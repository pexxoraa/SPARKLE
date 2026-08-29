const qs = (selector) => document.querySelector(selector);
const qsa = (selector) => [...document.querySelectorAll(selector)];
let state = null;

const escapeHtml = (value) => String(value).replace(
  /[&<>'"]/g,
  (character) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'}[character]),
);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {'Content-Type': 'application/json'},
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
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
      metric('Application builds', state.builders.workspaces),
      metric('Static verifications', state.builders.verifications),
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

refresh();
