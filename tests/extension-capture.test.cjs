const assert = require('node:assert/strict');
const { test } = require('node:test');
const { JSDOM } = require('../dashboard/node_modules/jsdom');
const { capture } = require('../extension/capture.js');
function document(html) {
  const dom = new JSDOM('<main>' + html + '</main>');
  dom.window.Element.prototype.getClientRects = () => [{}];
  return dom.window.document;
}
test('v2 preserves punctuation around adjacent inline code', () => {
  const d = document('<p>with <code>tzinfo</code> <code>None</code>.</p>');
  assert.equal(capture(d.querySelector('main')).text, 'with tzinfo None.');
});
test('v2 separates nested blocks without double-counting their text', () => {
  const d = document('<h2>Heading</h2><div><p>One <b>sentence</b>.</p><ul><li>First</li><li>Second</li></ul></div><p>One sentence.</p>');
  assert.equal(capture(d.querySelector('main')).text, 'Heading\nOne sentence.\nFirst\nSecond\nOne sentence.');
});
test('v2 records separate Sphinx method entries in Unicode code-point coordinates', () => {
  const d = document('<p>🌿 Unicode.</p><dl><dt id="a">method a()</dt><dd><p>Value.</p></dd></dl><dl><dt id="b">method b()</dt><dd><p>Other.</p></dd></dl>');
  const result = capture(d.querySelector('main'));
  assert.deepEqual(result.capture_entries.map(x => x.subject), ['a', 'b']);
  const chars = Array.from(result.text);
  for (const entry of result.capture_entries) assert.match(chars.slice(entry.start, entry.end).join(''), /^method/);
});
test('v2 keeps code lines, excludes private/hidden/non-content text, and bounds length', () => {
  const d = document('<pre>x = 1;\nx++;</pre><div hidden>SECRET</div><div data-alive-private>SECRET</div><nav>SECRET</nav><p style="display:none">SECRET</p><p>Visible العربية 中文.</p>');
  const result = capture(d.querySelector('main'));
  assert.equal(result.text, 'x = 1;\nx++;\nVisible العربية 中文.');
  assert.equal(Array.from(capture(d.querySelector('main'), 7).text).length, 7);
});
test('v2 binds the selected repeated occurrence, including a Unicode prefix', () => {
  const d = document('<p>🌿 Intro.</p><p>Remember this exact sentence.</p><p>Remember this exact sentence.</p>');
  const p = d.querySelectorAll('p')[2], range = d.createRange();
  range.selectNodeContents(p);
  const result = capture(d.querySelector('main'), 8000, range);
  const chars = Array.from(result.text);
  assert.equal(result.selection.quote, 'Remember this exact sentence.');
  assert.equal(chars.slice(result.selection.occurrence_start).join(''), result.selection.quote);
  assert.ok(result.selection.occurrence_start > Array.from(result.text).indexOf('R'));
});
