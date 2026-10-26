import base64
from urllib.parse import urlsplit

from playwright.async_api import async_playwright

from alive.models import BrowserSession, now, uid
from alive.schemas import Observation

SAFE_TEXT = """(selector) => {
 const root = document.querySelector(selector || 'body');
 const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
 const pieces = []; let node, size = 0;
 while ((node = walker.nextNode()) && size < 8000) {
   const el = node.parentElement;
   if (!el || el.closest('script,style,noscript,input,textarea,select,[contenteditable],'
     + '[hidden],[aria-hidden="true"],[data-alive-private]') || !el.getClientRects().length
     || getComputedStyle(el).visibility === 'hidden') continue;
   const text = node.textContent.trim(); pieces.push(text); size += text.length;
 }
 return pieces.join(' ').replace(/\\s+/g,' ').trim().slice(0,8000);
}"""


class Browsers:
    def __init__(self, kernel):
        self.kernel = kernel
        self.playwright = None
        self.browser = None
        self.pages = {}

    def allowed(self, url):
        parsed = urlsplit(url)
        if parsed.username or parsed.password or parsed.scheme not in ("http", "https"):
            return False
        origin = f"{parsed.scheme}://{parsed.netloc}"
        # Exact origins including ports; no wildcard hosts or arbitrary loopback ports.
        return origin in self.kernel.settings.alive_browser_origins

    async def create(self):
        if len(self.pages) >= 3:
            raise ValueError("Managed browser session limit reached")
        if not self.playwright:
            self.playwright = await async_playwright().start()
        if not self.browser:
            self.browser = await self.playwright.chromium.launch(
                channel="chrome", headless=self.kernel.settings.alive_headless
            )
        context = await self.browser.new_context(accept_downloads=False, service_workers="block")

        async def route(request_route):
            if self.allowed(request_route.request.url):
                await request_route.continue_()
            else:
                await request_route.abort()

        await context.route("**/*", route)
        page = await context.new_page()
        page.set_default_timeout(5000)
        page.on("popup", lambda popup: popup.close())
        session_id = uid()
        self.pages[session_id] = (context, page)
        k = self.kernel
        async with k.lock, k.db.sessions.begin() as session:
            session.add(BrowserSession(id=session_id, instance_id=k.instance_id))
            k.add_event(session, "browser.session_opened", {"session_id": session_id})
        return {"id": session_id, "status": "open", "current_url": "about:blank"}

    def page(self, session_id):
        if session_id not in self.pages:
            raise KeyError("Browser session is not open in this process")
        return self.pages[session_id][1]

    async def observe(self, session_id, event_type, selector="body"):
        page = self.page(session_id)
        payload = {
            "url": page.url.split("?")[0].split("#")[0],
            "title": await page.title(),
            "text": await page.evaluate(SAFE_TEXT, selector),
            "session_id": session_id,
        }
        await self.kernel.ingest(Observation(event_type=event_type, source="user", payload=payload))
        return payload

    async def navigate(self, session_id, url):
        if not self.allowed(url):
            raise PermissionError("Destination is not in ALIVE_BROWSER_ORIGINS")
        page = self.page(session_id)
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        if not self.allowed(page.url):
            raise PermissionError("Redirect destination is not authorised")
        k = self.kernel
        async with k.lock, k.db.sessions.begin() as session:
            row = await session.get(BrowserSession, session_id)
            row.current_url, row.updated_at = page.url, now()
            k.add_event(
                session, "browser.navigation_completed", {"session_id": session_id, "url": page.url}
            )
        return await self.observe(session_id, "browser.page_opened")

    async def action(self, session_id, data):
        page = self.page(session_id)
        if not self.allowed(page.url):
            raise PermissionError("Current page is not authorised")
        if data.operation == "screenshot":
            # Screenshots are allowed only on the controlled demo, never arbitrary sensitive pages.
            if urlsplit(page.url).path != "/demo":
                raise PermissionError("Screenshots are restricted to the local demonstration page")
            return {
                "image": "data:image/png;base64,"
                + base64.b64encode(await page.screenshot()).decode()
            }
        locator = page.locator(data.selector)
        if data.operation in ("click", "fill"):
            allowed = await locator.evaluate(
                """(el, op) =>
                el.dataset.aliveAllow?.split(' ').includes(op)
                && !el.matches('[type=password],[type=hidden],[autocomplete*=cc-]')
                && !el.closest('[data-alive-private]')""",
                data.operation,
            )
            if not allowed:
                raise PermissionError("Element does not explicitly permit this operation")
            if data.operation == "click":
                await locator.click()
            else:
                await locator.fill(data.value)
            await self.kernel.emit(
                "action.executed", {"operation": data.operation, "session_id": session_id}
            )
        elif data.selector != "body":
            if await locator.locator("input,textarea,[data-alive-private]").count():
                raise PermissionError("Selected subtree contains private fields")
            if await locator.evaluate("el => !!el.closest('input,textarea,[data-alive-private]')"):
                raise PermissionError("Private field inspection denied")
        return await self.observe(
            session_id,
            "browser.dom_changed",
            data.selector if data.operation == "inspect" else "body",
        )

    async def close_session(self, session_id):
        pair = self.pages.pop(session_id, None)
        if pair:
            await pair[0].close()
        k = self.kernel
        async with k.lock, k.db.sessions.begin() as session:
            row = await session.get(BrowserSession, session_id)
            if not row:
                raise KeyError("Unknown browser session")
            row.status, row.updated_at = "closed", now()
            k.add_event(session, "browser.session_closed", {"session_id": session_id})

    async def close(self):
        for session_id in list(self.pages):
            await self.close_session(session_id)
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
