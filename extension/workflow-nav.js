import { workflowURL } from './workflow-link.js';
import { DEFAULT_BACKEND } from './config.js';
const element = id => document.getElementById(id);
element('workflow-open').onclick = async () => {
  try {
    const { backend = DEFAULT_BACKEND } = await chrome.storage.local.get('backend');
    const url = workflowURL(backend, {
      workflow: element('workflow-name').value.trim(),
      version: element('workflow-version').value.trim(),
      run: element('workflow-run').value.trim(),
      stage: element('workflow-stage').value.trim(),
    });
    await chrome.tabs.create({ url });
    element('workflow-status').textContent = 'Opened read-only inspection. Authenticate in the dashboard.';
  } catch (error) {
    element('workflow-status').textContent = error.message;
  }
};
