export const DEFAULT_BACKEND = 'http://127.0.0.1:8000';
export const DEFAULT_BACKENDS = [DEFAULT_BACKEND, 'http://localhost:8000'];
export const AUTHORISED_PAGES = [
  'https://docs.python.org/3/tutorial/',
  'https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide',
];

export function isLocalDemo(url) {
  return /^http:\/\/(127\.0\.0\.1|localhost):8000\/demo$/.test(url || '');
}
