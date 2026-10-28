(() => {
  if (globalThis.__aliveObserver) return;
  let previous = "",
    lastSent = 0;
  function snapshot() {
    const content = document.querySelector('main,article,[role="main"]') || document.body;
    const captured = globalThis.__aliveCaptureV2(content);
    const text = captured.text;
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
          ...captured,
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
