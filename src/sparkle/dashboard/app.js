const qs = (selector) => document.querySelector(selector);
const qsa = (selector) => [...document.querySelectorAll(selector)];
let state = null;
let csrfToken = null;
let sessionRequired = false;

const escapeHtml = (value) => String(value).replace(
  /[&<>'"]/g,
  (character) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'}[character]),
);

async function api(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const headers = {'Content-Type': 'application/json', ...(options.headers || {})};
  if (csrfToken && !['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    headers['X-SPARKLE-CSRF'] = csrfToken;
  }
  const response = await fetch(path, {
    credentials: 'same-origin',
    ...options,
    headers,
  });
  const data = await response.json();
  if (response.status === 401 && path !== '/api/session/login') {
    csrfToken = null;
    showAuthGate('Your session is missing or expired.');
  }
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

function showAuthGate(message = '') {
  qs('#loginError').textContent = message;
  qs('#authGate').hidden = false;
  qs('#logoutButton').hidden = true;
  qs('#loginToken').focus();
}

function hideAuthGate() {
  qs('#loginError').textContent = '';
  qs('#authGate').hidden = true;
}

async function initializeSession() {
  try {
    const session = await api('/api/session');
    sessionRequired = session.authentication_required;
    csrfToken = session.csrf_token || null;
    if (sessionRequired && !session.authenticated) {
      showAuthGate(session.session_auth_enabled
        ? ''
        : 'Dashboard sessions are disabled; use a bearer-authenticated API client.');
      return;
    }
    hideAuthGate();
    qs('#logoutButton').hidden = session.authentication_mode !== 'session';
    await refresh();
  } catch (error) {
    showAuthGate('Unable to check the server session.');
  }
}

function metric(label, value) {
  return `<div class="card metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function empty(message) {
  return `<div class="list-item"><small>${escapeHtml(message)}</small></div>`;
}

async function refresh() {
  try {
    state = (await api('/api/health')).status;
    qs('#statusDot').classList.add('ready');
    qs('#systemLabel').textContent = state.status === 'ready'
      ? 'All core systems ready'
      : 'Core ready · provider key missing';
    qs('#activeModel').textContent = state.models[0]?.model_id || state.active_model;
    qs('#statusGrid').innerHTML = [
      metric('System', state.status),
      metric('Memory', `${state.memory.records} records`),
      metric('Knowledge', `${state.knowledge.sources} sources`),
      metric('Generated agents', state.generated_agents.count),
      metric('Automation runs', state.automation.recent_runs),
      metric('Automation service', state.automation.service.state),
      metric('Application builds', state.builders.workspaces),
      metric('Static verifications', state.builders.verifications),
      metric('Workspace test runs', state.builders.test_runs),
      metric('External worker runs', state.builders.external_worker_runs),
      metric('Application artifacts', state.builders.artifacts),
      metric('Deployment records', state.builders.deployment_records),
      metric('API audit records', state.api_security.recent_audit_records),
    ].join('');
    qs('#agentList').innerHTML = state.agents.map((agent) => (
      `<span>${escapeHtml(agent.name)}${agent.source === 'generated' ? ' · generated' : ''}</span>`
    )).join('');
  } catch (error) {
    qs('#systemLabel').textContent = 'Connection failed';
  }
}

async function loadPanel(panel) {
  if (panel === 'memory') {
    const data = await api('/api/memory?limit=50');
    qs('#memoryList').innerHTML = data.memories.length
      ? data.memories.map((memory) => (
        `<div class="list-item"><strong>${escapeHtml(memory.key)}</strong><small>${escapeHtml(memory.category)} · ${escapeHtml(memory.value)}</small></div>`
      )).join('')
      : empty('No durable memories stored.');
  }
  if (panel === 'automations') {
    const data = await api('/api/automation-runs?limit=50');
    qs('#automationList').innerHTML = data.runs.length
      ? data.runs.map((run) => (
        `<div class="list-item"><strong>${escapeHtml(run.name)} · ${escapeHtml(run.status)}</strong><small>${escapeHtml(run.trace_id || 'no agent trace')} · ${escapeHtml(run.attempts)} attempt(s)</small></div>`
      )).join('')
      : empty('No automations executed yet.');
  }
  if (panel === 'builds') {
    const data = await api('/api/builds?limit=50');
    qs('#buildList').innerHTML = data.builds.length
      ? data.builds.map((build) => (
        `<div class="list-item"><strong>${escapeHtml(build.project_name)} · ${escapeHtml(build.status)}</strong><small>${escapeHtml(build.files.length)} files · ${escapeHtml(build.total_bytes)} bytes</small></div>`
      )).join('')
      : empty('No application workspaces generated yet.');
  }
  if (panel === 'verifications') {
    const data = await api('/api/verifications?limit=50');
    qs('#verificationList').innerHTML = data.verifications.length
      ? data.verifications.map((verification) => (
        `<div class="list-item"><strong>${escapeHtml(verification.project_name)} · ${escapeHtml(verification.status)}</strong><small>${escapeHtml(verification.passed)} passed · ${escapeHtml(verification.failed)} failed · ${escapeHtml(verification.duration_ms)} ms</small></div>`
      )).join('')
      : empty('No workspace verifications recorded yet.');
  }
  if (panel === 'tests') {
    const data = await api('/api/test-runs?limit=50');
    qs('#testRunList').innerHTML = data.test_runs.length
      ? data.test_runs.map((run) => (
        `<div class="list-item"><strong>${escapeHtml(run.project_name)} · ${escapeHtml(run.status)}</strong><small>${escapeHtml(run.framework)} · exit ${escapeHtml(run.returncode)} · ${escapeHtml(run.duration_ms)} ms${run.timed_out ? ' · timed out' : ''}</small></div>`
      )).join('')
      : empty('No workspace tests executed yet.');
  }
  if (panel === 'external-tests') {
    const data = await api('/api/external-test-runs?limit=50');
    qs('#externalTestRunList').innerHTML = data.external_test_runs.length
      ? data.external_test_runs.map((run) => (
        `<div class="list-item"><strong>${escapeHtml(run.project_name)} · ${escapeHtml(run.status)}</strong><small>${escapeHtml(run.framework)} · signed response ${escapeHtml(run.response_verified)} · isolation verified ${escapeHtml(run.isolation_verified)} · ${escapeHtml(run.duration_ms)} ms</small></div>`
      )).join('')
      : empty('No external worker submissions recorded yet.');
  }
  if (panel === 'releases') {
    const [artifactData, deploymentData] = await Promise.all([
      api('/api/artifacts?limit=50'),
      api('/api/deployments?limit=50'),
    ]);
    qs('#artifactList').innerHTML = artifactData.artifacts.length
      ? artifactData.artifacts.map((artifact) => (
        `<div class="list-item"><strong>${escapeHtml(artifact.project_name)} · ${escapeHtml(artifact.status)}</strong><small>${escapeHtml(artifact.file_count)} files · SHA-256 ${escapeHtml(artifact.artifact_sha256)}</small></div>`
      )).join('')
      : empty('No application artifacts packaged yet.');
    qs('#deploymentList').innerHTML = deploymentData.deployments.length
      ? deploymentData.deployments.map((deployment) => (
        `<div class="list-item"><strong>${escapeHtml(deployment.project_name)} · ${escapeHtml(deployment.reported_outcome)}</strong><small>${escapeHtml(deployment.environment_name)} · ${escapeHtml(deployment.target_kind)} · ${escapeHtml(deployment.verification_status)}</small></div>`
      )).join('')
      : empty('No deployment events recorded yet.');
  }
  if (panel === 'traces') {
    const data = await api('/api/traces?limit=50');
    qs('#traceList').innerHTML = data.traces.length
      ? data.traces.map((trace) => (
        `<div class="list-item"><strong>${escapeHtml(trace.trace_id)} · ${escapeHtml(trace.status)}</strong><small>${escapeHtml(trace.agent || '—')} · ${escapeHtml(trace.model || '—')} · ${escapeHtml(trace.duration_ms || 0)} ms</small></div>`
      )).join('')
      : empty('No executions traced yet.');
  }
  if (panel === 'audit') {
    const data = await api('/api/audit?limit=50');
    qs('#auditList').innerHTML = data.audit.length
      ? data.audit.map((record) => (
        `<div class="list-item"><strong>${escapeHtml(record.method)} ${escapeHtml(record.path)} · ${escapeHtml(record.status)}</strong><small>${escapeHtml(record.outcome)} · ${escapeHtml(record.duration_ms)} ms · ${escapeHtml(record.created_at)}</small></div>`
      )).join('')
      : empty('No API requests audited yet.');
  }
}

qsa('nav button').forEach((button) => button.addEventListener('click', async () => {
  qsa('nav button').forEach((item) => item.classList.remove('active'));
  qsa('.panel').forEach((panel) => panel.classList.remove('active'));
  button.classList.add('active');
  qs(`#${button.dataset.panel}`).classList.add('active');
  qs('#panelTitle').textContent = button.textContent;
  try {
    await loadPanel(button.dataset.panel);
  } catch (error) {
    qs('#systemLabel').textContent = `Panel failed: ${error.message}`;
  }
}));

qs('#chatForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const input = qs('#messageInput');
  const button = event.currentTarget.querySelector('button');
  const message = input.value.trim();
  if (!message) return;
  qs('#conversation').insertAdjacentHTML(
    'beforeend',
    `<div class="message user-message">${escapeHtml(message)}</div>`,
  );
  input.value = '';
  button.disabled = true;
  button.textContent = 'Working…';
  try {
    const data = await api('/api/chat', {
      method: 'POST',
      body: JSON.stringify({message, multi_agent: qs('#multiAgent').checked}),
    });
    const result = data.result;
    qs('#conversation').insertAdjacentHTML(
      'beforeend',
      `<div class="message assistant-message">${escapeHtml(result.text)}<small>${escapeHtml(result.agent)} · ${escapeHtml(result.trace_id)}</small></div>`,
    );
  } catch (error) {
    qs('#conversation').insertAdjacentHTML(
      'beforeend',
      `<div class="message assistant-message">${escapeHtml(error.message)}<small>Execution failed</small></div>`,
    );
  } finally {
    button.disabled = false;
    button.innerHTML = 'Execute <span>→</span>';
    qs('#conversation').scrollTop = qs('#conversation').scrollHeight;
    refresh();
  }
});

qs('#loginForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const input = qs('#loginToken');
  const button = event.currentTarget.querySelector('button');
  const token = input.value;
  input.value = '';
  button.disabled = true;
  try {
    const session = await api('/api/session/login', {
      method: 'POST',
      headers: {Authorization: `Bearer ${token}`},
    });
    csrfToken = session.csrf_token;
    sessionRequired = true;
    hideAuthGate();
    qs('#logoutButton').hidden = false;
    await refresh();
  } catch (error) {
    showAuthGate('Authentication failed.');
  } finally {
    button.disabled = false;
  }
});

qs('#logoutButton').addEventListener('click', async () => {
  try {
    await api('/api/session/logout', {method: 'POST'});
  } finally {
    csrfToken = null;
    if (sessionRequired) showAuthGate('Session ended.');
  }
});

initializeSession();
