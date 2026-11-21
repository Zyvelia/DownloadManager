'use strict';
const $ = id => document.getElementById(id);
const session = document.querySelector('meta[name="zdm-session"]').content;
const labels = {speed: 'Transfer speed', browser: 'Browser extension', recent: 'Recent downloads', details: 'Transfer details'};
const defaults = ['speed', 'browser'];
let state, draft, selected, dragging, noticeTimer;
let view = 'Downloads', filter = 'All';
let chartWindow = 5;
const dateTime = seconds => new Date(seconds * 1000).toLocaleString();
const escape = value => String(value ?? '').replace(/[&<>"']/g, char =>
  ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'})[char]);
const rate = bytes => bytes >= 1048576 ? (bytes / 1048576).toFixed(1) + ' MiB/s' : Math.round(bytes / 1024) + ' KiB/s';
const eta = job => job.speed && job.size ? new Date(Math.min(86399, Math.ceil(Math.max(0, job.size - job.received) / job.speed)) * 1000).toISOString().slice(11, 19) : '—';
function html(node, markup) {
  if (node.lastMarkup !== markup) {
    node.innerHTML = markup;
    node.lastMarkup = markup;
  }
}
async function api(path, value) {
  const response = await fetch('/api/' + path, {
    method: value ? 'POST' : 'GET',
    headers: {Authorization: 'Bearer ' + session, 'Content-Type': 'application/json'},
    body: value ? JSON.stringify(value) : undefined,
  });
  const result = await response.json();
  if (!response.ok) throw Error(result.error);
  return result;
}
function notice(message) {
  clearTimeout(noticeTimer);
  $('notice').textContent = message;
  $('notice').hidden = false;
  noticeTimer = setTimeout(() => $('notice').hidden = true, 6000);
}
async function update() {
  state = await api('state');
  if (!$('add-form').dataset.ready) {
    $('add-form').elements.destination.value = state.destination;
    $('add-form').dataset.ready = 'true';
  }
  render();
}
async function mutate(path, data, success) {
  try {
    await api(path, data);
    await update();
    if (success) notice(success);
    return true;
  } catch (error) {
    notice(error.message);
    return false;
  }
}
function show(next) {
  view = next;
  if (view === 'Settings') {
    for (const key of ['destination', 'parallel', 'limit']) $('settings-form').elements[key].value = state[key];
  }
  render();
}
function render() {
  if (!state) return;
  const home = view === 'Downloads';
  const schedule = view === 'Scheduler';
  const history = view === 'History';
  const active = state.jobs.filter(job => ['Downloading', 'Pausing'].includes(job.status));
  const completed = state.jobs.filter(job => job.status === 'Completed');
  const total = active.reduce((sum, job) => sum + job.speed, 0);
  for (const button of document.querySelectorAll('nav button')) button.setAttribute('aria-current', button.dataset.view === view);
  $('title').textContent = home ? 'Z’s Download Manager' : view;
  $('subtitle').textContent = home ? (draft ? 'Drag panels to rearrange, or restore them from Hidden panels.' : active.length + ' downloading') : '';
  $('layout-actions').hidden = !home;
  $('customize').hidden = !!draft;
  $('reset').hidden = $('done').hidden = !draft;
  $('add').hidden = !(home || schedule);
  $('add-title').textContent = schedule ? 'Schedule a download' : 'Add download';
  $('schedule-field').hidden = !schedule;
  $('add-form').elements.when.required = schedule;
  $('submit-download').textContent = schedule ? 'Schedule download' : 'Add to queue';
  $('workspace').hidden = !(home || schedule || history);
  $('extension').hidden = view !== 'Browser Extension';
  $('settings').hidden = view !== 'Settings';
  $('extension-status').textContent = state.connected ? 'Connected to the browser extension.' : 'Waiting for the browser extension.';
  if ($('key').value !== state.key) $('key').value = state.key;
  $('summary').textContent = 'Queue: ' + state.jobs.length + ' items (' + active.length + ' downloading, ' + completed.length + ' completed)';
  $('speed-total').textContent = 'Total speed: ' + rate(total);
  const presets = [0, 512, 1024, 5120];
  html($('limit'), [...new Set([...presets, state.limit])].map(value => '<option value="' + value + '">' + (value ? value + ' KiB/s' : 'Off') + '</option>').join(''));
  $('limit').value = state.limit;
  if ($('workspace').hidden) return;

  const candidates = {All: state.jobs, Active: active, Completed: completed};
  const jobs = schedule ? state.jobs.filter(job => job.status === 'Scheduled') : history ? completed : candidates[filter];
  $('queue-title').textContent = schedule ? 'Scheduled downloads' : history ? 'Completed downloads' : 'Download queue';
  $('time-label').textContent = schedule ? 'Starts' : 'ETA';
  $('filters').hidden = $('hold').hidden = !home;
  html($('filters'), Object.entries(candidates).map(([key, list]) =>
    '<button data-filter="' + key + '" aria-pressed="' + (key === filter) + '">' + key + ' (' + list.length + ')</button>').join(''));
  $('hold').textContent = state.hold ? '▶  Resume queue' : 'Ⅱ  Pause all';
  $('hold').disabled = state.jobs.some(job => job.status === 'Pausing');
  $('empty').hidden = !!jobs.length;
  $('empty-title').textContent = !jobs.length && home && filter === 'All' ? 'No downloads yet' : 'No ' + (schedule ? 'scheduled' : history || filter === 'Completed' ? 'completed' : 'active') + ' downloads';
  $('empty-hint').textContent = home && filter === 'All' ? 'Paste a direct link above or send one from the browser extension.' : '';
  html($('rows'), jobs.map((job, index) => {
    const percent = job.status === 'Completed' ? 100 : job.size ? Math.min(100, Math.floor(job.received / job.size * 100)) : null;
    const action = ['Downloading', 'Queued'].includes(job.status) ? ['pause', 'Pause', 'Ⅱ'] :
      ({Paused: ['start', 'Resume', '▶'], Failed: ['start', 'Retry', '↻'], Scheduled: ['start', 'Start now', '▶']})[job.status];
    const note = job.error || (job.source === 'Browser' ? 'Sent from browser' : '');
    return '<tr data-job="' + job.id + '" class="' + (selected === job.id ? 'selected' : '') + '"><td>' + (index + 1) +
      '</td><td><span class="filename">' + escape(job.name) + '</span>' + (note ? '<small class="row-note">' + escape(note) + '</small>' : '') +
      '</td><td>' + (percent === null ? '—' : '<span class="progress"><progress max="100" value="' + percent + '" aria-label="Download progress"></progress>' + percent + '%</span>') +
      '</td><td>' + (job.speed ? rate(job.speed) : '—') + '</td><td>' + (schedule ? escape(dateTime(job.scheduled)) : eta(job)) +
      '</td><td><span class="badge ' + job.status + '">' + job.status + '</span></td><td>' +
      (action ? '<button class="row-action" data-action="' + action[0] + '" title="' + action[1] + '" aria-label="' + action[1] + ' ' + escape(job.name) + '">' + action[2] + '</button>' : '') + '</td></tr>';
  }).join(''));
  $('panels').hidden = !home;
  const layout = draft || state.panels;
  $('workspace').classList.toggle('wide', !home || (!layout.length && !draft));
  if (home) renderPanels(layout, total, completed);
}
function panelContent(key, total, completed) {
  if (key === 'speed') return '<div class="speed-head"><strong>' + rate(total) + '</strong><select id="chart-window" aria-label="Speed history range"><option value="1"' + (chartWindow === 1 ? ' selected' : '') + '>Last minute</option><option value="5"' + (chartWindow === 5 ? ' selected' : '') + '>Last 5 minutes</option></select></div><canvas width="380" height="117" role="img" aria-label="Download speed history"></canvas>';
  if (key === 'browser') return '<div class="connection-line"><span class="badge ' + (state.connected ? 'connected' : '') + '">' +
    (state.connected ? '● Connected' : '○ Disconnected') + '</span><button data-manage>Manage…</button></div>' +
    '<dl class="info"><dt>Last link received</dt><dd>' + escape(state.last?.name || '—') + '</dd><dt>Received</dt><dd>' +
    (state.last ? escape(dateTime(state.last.time)) : '—') + '</dd></dl>';
  if (key === 'recent') return completed.length ? '<ul class="recent">' + completed.slice(-5).reverse().map(job => '<li>' + escape(job.name) + '</li>').join('') + '</ul>' : '<span class="muted">No completed downloads.</span>';
  const job = state.jobs.find(item => item.id === selected);
  return job ? '<dl class="info"><dt>File</dt><dd>' + escape(job.name) + '</dd><dt>Source</dt><dd>' + escape(job.source) +
    '</dd><dt>Destination</dt><dd>' + escape(job.destination) + '</dd><dt>Status</dt><dd>' + job.status +
    '</dd><dt>Downloaded</dt><dd>' + job.received.toLocaleString() + ' bytes</dd></dl>' :
    '<span class="muted">Select a download to see its details.</span>';
}
function renderPanels(layout, total, completed) {
  if (dragging || $('panels').contains(document.activeElement) && document.activeElement.id === 'chart-window') return;
  const markup = layout.map(key => '<section class="panel" data-panel="' + key + '"><div class="panel-head">' +
    (draft ? '<span class="grip" draggable="true" title="Drag to reorder" aria-hidden="true">⠿</span>' : '') +
    '<h2>' + labels[key] + '</h2>' + (draft ?
    '<button data-move="' + key + '" title="Move up" aria-label="Move ' + labels[key] + ' up"' + (layout[0] === key ? ' disabled' : '') + '>↑</button><button data-hide="' + key + '" title="Hide panel" aria-label="Hide ' + labels[key] + '">×</button>' : '') +
    '</div>' + panelContent(key, total, completed) + '</section>').join('');
  const missing = Object.keys(labels).filter(key => !layout.includes(key));
  html($('panels'), markup + (draft ? '<section class="panel"><h2>Hidden panels</h2>' +
    (missing.length ? missing.map(key => '<div class="hidden-row">' + labels[key] + '<button data-add="' + key + '" aria-label="Add ' + labels[key] + '">＋ Add</button></div>').join('') :
    '<p class="muted">All panels are visible.</p>') + '</section>' : ''));
  const canvas = $('panels').querySelector('canvas');
  if (canvas) draw(canvas);
}
function draw(canvas) {
  const context = canvas.getContext('2d');
  const width = canvas.width, height = canvas.height;
  const count = chartWindow * 120;
  const samples = state.history.slice(-count);
  const top = Math.max(1024, ...samples) * 1.2;
  context.clearRect(0, 0, width, height);
  context.font = '11px system-ui';
  context.strokeStyle = '#483952';
  context.fillStyle = '#cbb9d7';
  for (let i = 0; i <= 4; i++) {
    const y = 9 + i * 24;
    context.fillText(rate(top * (1 - i / 4)), 0, y + 3);
    context.beginPath();
    context.moveTo(72, y);
    context.lineTo(width, y);
    context.stroke();
  }
  const x = index => 72 + (width - 73) * (count - samples.length + index) / (count - 1);
  const y = value => 105 - (value / top) * 96;
  context.beginPath();
  samples.forEach((sample, index) => index ? context.lineTo(x(index), y(sample)) : context.moveTo(x(index), y(sample)));
  context.strokeStyle = '#d783fb';
  context.lineWidth = 2;
  context.stroke();
}
document.querySelector('nav').onclick = event => {
  const button = event.target.closest('[data-view]');
  if (button && state) show(button.dataset.view);
};
$('browse').onclick = async () => {
  $('browse').disabled = true;
  try {
    const result = await api('folder', {});
    if (result.destination) $('destination').value = result.destination;
  } catch (error) {
    notice(error.message);
  } finally {
    $('browse').disabled = false;
  }
};
$('add-form').onsubmit = async event => {
  event.preventDefault();
  const fields = event.target.elements;
  const scheduled = view === 'Scheduler' ? new Date(fields.when.value).getTime() / 1000 : 0;
  if (view === 'Scheduler' && !(scheduled > Date.now() / 1000)) return notice('Choose a future start time.');
  $('submit-download').disabled = true;
  if (await mutate('add', {url: fields.url.value, destination: fields.destination.value, scheduled}, scheduled ? 'Download scheduled.' : 'Added to the queue.')) {
    fields.url.value = '';
    fields.when.value = '';
    if (view === 'Downloads') { filter = 'All'; render(); }
  }
  $('submit-download').disabled = false;
};
$('settings-form').onsubmit = async event => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target));
  if (await mutate('settings', data, 'Settings saved.')) $('add-form').elements.destination.value = state.destination;
};
$('limit').onchange = event => mutate('settings', {destination: state.destination, parallel: state.parallel, limit: event.target.value});
$('hold').onclick = () => mutate('hold', {hold: !state.hold});
$('filters').onclick = event => {
  if (event.target.dataset.filter) { filter = event.target.dataset.filter; render(); }
};
$('rows').onclick = event => {
  const row = event.target.closest('[data-job]');
  if (!row) return;
  selected = row.dataset.job;
  if (event.target.dataset.action) mutate('action', {id: selected, action: event.target.dataset.action});
  else render();
};
$('customize').onclick = () => { draft = [...state.panels]; render(); };
$('reset').onclick = () => { draft = [...defaults]; render(); };
$('done').onclick = async () => {
  if (await mutate('panels', {panels: draft}, 'Layout saved.')) { draft = null; render(); }
};
$('panels').onclick = event => {
  const {add, hide, move, manage} = event.target.dataset;
  if (manage !== undefined) return show('Browser Extension');
  if (!draft) return;
  if (add) draft.push(add);
  if (hide) draft = draft.filter(key => key !== hide);
  if (move) {
    const index = draft.indexOf(move);
    if (index > 0) [draft[index - 1], draft[index]] = [draft[index], draft[index - 1]];
  }
  render();
};
$('panels').onchange = event => {
  if (event.target.id === 'chart-window') {
    chartWindow = Number(event.target.value);
    draw($('panels').querySelector('canvas'));
  }
};
$('panels').ondragstart = event => {
  if (!event.target.matches('.grip')) return;
  dragging = event.target.closest('[data-panel]').dataset.panel;
  event.dataTransfer.setData('text/plain', dragging);
  event.dataTransfer.effectAllowed = 'move';
};
$('panels').ondragover = event => {
  const target = event.target.closest('[data-panel]');
  if (!dragging || !target || target.dataset.panel === dragging) return;
  event.preventDefault();
  target.classList.add('drag-over');
};
$('panels').ondragleave = event => {
  const target = event.target.closest('[data-panel]');
  if (target && !target.contains(event.relatedTarget)) target.classList.remove('drag-over');
};
$('panels').ondrop = event => {
  const target = event.target.closest('[data-panel]');
  if (!dragging || !target) return;
  event.preventDefault();
  const position = draft.indexOf(target.dataset.panel);
  draft.splice(draft.indexOf(dragging), 1);
  draft.splice(position, 0, dragging);
  dragging = null;
  render();
};
$('panels').ondragend = () => {
  dragging = null;
  $('panels').querySelectorAll('.drag-over').forEach(panel => panel.classList.remove('drag-over'));
  render();
};
$('copy').onclick = async () => {
  try { await navigator.clipboard.writeText(state.key); notice('Connection key copied.'); }
  catch { $('key').select(); notice('Press Ctrl+C to copy the selected key.'); }
};
async function poll() {
  try { await update(); }
  catch { $('summary').textContent = 'Local service disconnected.'; }
  setTimeout(poll, 900);
}
poll();
