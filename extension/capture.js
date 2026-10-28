// Capture v2: block/entry boundaries, inline fidelity, Unicode code-point offsets.
// Runs in Chrome's isolated content-script world; it never grants permission.
(function (root) {
  const excluded = 'script,style,noscript,nav,input,textarea,select,[contenteditable],'
    + '[hidden],[aria-hidden="true"],[data-alive-private],.headerlink';
  const blocks = new Set(['ADDRESS','ARTICLE','ASIDE','BLOCKQUOTE','DD','DIV','DL','DT',
    'FIGCAPTION','FIGURE','H1','H2','H3','H4','H5','H6','LI','MAIN','OL','P','PRE','SECTION','TABLE','TR','UL']);
  function capture(element, limit = 8000, selection = null) {
    const view = element.ownerDocument.defaultView;
    let text = '';
    const points = [], entries = [];
    const boundary = () => {
      while (text.endsWith(' ')) { text = text.slice(0, -1); points.pop(); }
      if (text && !text.endsWith('\n')) { text += '\n'; points.push(null); }
    };
    function raw(node, pre) {
      const value = node.nodeValue;
      for (let i = 0; i < value.length && text.length < limit * 2; i++) {
        let char = value[i];
        if (pre && char === '\n') { boundary(); continue; }
        if (!pre && /[\t\r\n\f\v ]/.test(char)) char = ' ';
        if (!pre && char === ' ' && (!text || /[ \n]$/.test(text))) continue;
        text += char;
        points.push({ node, offset: i });
      }
    }
    function walk(node, pre = false) {
      if (node.nodeType === 3) { raw(node, pre); return; }
      if (node.nodeType !== 1 && node.nodeType !== 11) return;
      if (node.nodeType === 1) {
        if (node.matches(excluded)) return;
        const style = view.getComputedStyle(node);
        if (style.display === 'none' || style.visibility === 'hidden' || style.visibility === 'collapse') return;
        if (!node.getClientRects().length) return;
      }
      const block = blocks.has(node.tagName);
      if (block || node.tagName === 'BR') boundary();
      const dt = node.tagName === 'DL' ? Array.from(node.children).find(child => child.tagName === 'DT' && child.id) : null;
      const start = text.length;
      for (const child of node.childNodes) walk(child, pre || node.tagName === 'PRE');
      if (dt) entries.push({ subject: dt.id, start, end: text.trimEnd().length });
      if (block) boundary();
    }
    walk(element);
    text = Array.from(text.trimEnd()).slice(0, limit).join('');
    const cp = index => Array.from(text.slice(0, index)).length;
    const result = { text, capture_format_version: 2,
      capture_entries: entries.filter(entry => entry.start < text.length).map(entry => ({
        subject: entry.subject, start: cp(entry.start), end: cp(Math.min(entry.end, text.length)),
      })) };
    if (selection && !selection.collapsed) {
      const offsets = [];
      for (let i = 0; i < Math.min(points.length, text.length); i++) {
        const point = points[i];
        if (!point) continue;
        try {
          if (selection.comparePoint(point.node, point.offset) === 0 &&
              selection.comparePoint(point.node, point.offset + 1) === 0) offsets.push(i);
        } catch { /* A selection outside this retained root is not an anchor. */ }
      }
      if (offsets.length) {
        let start = offsets[0], end = offsets[offsets.length - 1] + 1;
        while (start < end && /\s/.test(text[start])) start++;
        while (end > start && /\s/.test(text[end - 1])) end--;
        result.selection = { quote: text.slice(start, end), occurrence_start: cp(start) };
      }
    }
    return result;
  }
  root.__aliveCaptureV2 = capture;
  if (typeof module !== 'undefined') module.exports = { capture };
})(globalThis);
