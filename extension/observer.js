(() => {
  if (globalThis.__aliveObserver) return;
  let previous = "",
    lastSent = 0;
  function snapshot() {
    const walker = document.createTreeWalker(
      document.querySelector('main,article,[role="main"]') || document.body,
      NodeFilter.SHOW_TEXT,
    );
    const pieces = [];
    let node;
    while ((node = walker.nextNode()) && pieces.join(" ").length < 8000) {
      const el = node.parentElement;
      if (
        !el ||
        el.closest(
          'script,style,noscript,nav,input,textarea,select,[contenteditable],[hidden],[aria-hidden="true"],[data-alive-private]',
        ) ||
        !el.getClientRects().length
      )
        continue;
      if (getComputedStyle(el).visibility === "hidden") continue;
      const text = node.textContent.trim();
      if (text) pieces.push(text);
    }
    const text = pieces.join(" ").replace(/\s+/g, " ").slice(0, 8000);
    if (text === previous) return;
    previous = text;
    lastSent = Date.now();
    // Deliberately omit URL query/fragment which may contain authentication material.
    chrome.runtime
      .sendMessage({
        type: "observation",
        payload: {
          url: location.origin + location.pathname,
          title: document.title.slice(0, 200),
          text,
        },
      })
      .catch(() => {});
  }
  globalThis.__aliveObserver = new MutationObserver(() => {
    if (globalThis.__aliveTimer) return;
    globalThis.__aliveTimer = setTimeout(
      () => {
        globalThis.__aliveTimer = null;
        snapshot();
      },
      Math.max(750, 2000 - (Date.now() - lastSent)),
    );
  });
  globalThis.__aliveObserver.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true,
  });
  snapshot();
})();
