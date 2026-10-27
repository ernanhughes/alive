const $ = (id) => document.getElementById(id);
const saved = await chrome.storage.local.get(["backend", "token", "autoSend"]);
$("backend").value = saved.backend || "http://127.0.0.1:8000";
$("token").value = saved.token || "";
$("auto").checked = !!saved.autoSend;
async function command(type) {
  const response = await chrome.runtime.sendMessage({ type });
  if (response.error) throw new Error(response.error);
  return response.data;
}
async function action(fn) {
  try {
    await fn();
  } catch (e) {
    $("status").textContent = e.message;
  }
}
$("connect").onclick = () =>
  action(async () => {
    await chrome.storage.local.set({
      backend: $("backend").value.replace(/\/$/, ""),
      token: $("token").value,
    });
    const state = await command("connect");
    $("state").textContent = JSON.stringify(state, null, 2);
    $("status").textContent = "Connected · " + state.identity.name;
  });
$("auto").onchange = () =>
  chrome.storage.local.set({ autoSend: $("auto").checked });
$("start").onclick = () =>
  action(async () => {
    await command("start");
    $("status").textContent =
      "Observing this page · explicit permission active";
  });
$("stop").onclick = () =>
  action(async () => {
    await command("stop");
    $("preview").textContent = "Observation permission revoked.";
    $("status").textContent = "Stopped · page observation revoked";
  });
$("send").onclick = () =>
  action(async () => {
    await command("send");
    $("status").textContent = "Observation persisted by ALIVE";
  });
async function preview() {
  const { latest } = await chrome.storage.session.get("latest");
  if (latest)
    $("preview").textContent = JSON.stringify(latest.payload, null, 2);
}
chrome.storage.onChanged.addListener(preview);
preview();

$("connect").disabled = false;
$("token").disabled = false;
$("backend").disabled = false;
