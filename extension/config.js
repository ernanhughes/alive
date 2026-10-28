export const DEFAULT_BACKEND = 'http://127.0.0.1:8000';
export const DEFAULT_BACKENDS = [DEFAULT_BACKEND, 'http://localhost:8000'];
const NOTEBOOK_CHAPTERS = [
  'alive-11-corrections', 'alive-12-status', 'alive-13-status',
  'alive-13-what-was-wrong', 'alive-14-status',
];
export const AUTHORISED_PAGES = [
  ...['127.0.0.1', 'localhost'].flatMap(host =>
    ['python-3.11.html', 'python-3.12.html', 'synthetic-no-change.html']
      .map(name => `http://${host}:8000/demo-live-01/${name}`)),
  'https://docs.python.org/3.11/library/datetime.html',
  'https://docs.python.org/3.12/library/datetime.html',
  // ALIVE Notebook (site/): exact chapter URLs of a Hugo site served on loopback port 1313.
  ...['127.0.0.1', 'localhost'].flatMap(host =>
    NOTEBOOK_CHAPTERS.map(chapter => `http://${host}:1313/chapters/${chapter}/`)),
  'https://docs.python.org/3/tutorial/',
  'https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide',
];

export function isLocalDemo(url) {
  return /^http:\/\/(127\.0\.0\.1|localhost):8000\/demo$/.test(url || '');
}
