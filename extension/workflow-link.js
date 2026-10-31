// Navigation only. Identifiers never grant authority or carry browser context.
export function workflowURL(backend, { workflow, version, run, stage }) {
  if (!['http://127.0.0.1:8000', 'http://localhost:8000'].includes(backend))
    throw new Error('Use an allowed local ALIVE backend');
  if (!/^[a-z][a-z0-9-]{2,63}$/.test(workflow || '') ||
      !/^[1-9]\d{0,6}$/.test(String(version)) || Number(version) > 1000000 ||
      (run && !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(run)) ||
      (stage && !/^[a-z][a-z0-9_]{0,31}$/.test(stage)))
    throw new Error('Enter a valid workflow, version and optional run/stage identifiers');
  const params = new URLSearchParams({ workflow, version: String(version) });
  if (run) params.set('run', run);
  if (stage) params.set('stage', stage);
  return backend + '/#workflows?' + params;
}
