/**
 * NotifySeat Web Application
 * Local Transport Seat & Cancellation Radar
 */

let currentTransport = 'tcdd';
let isEngineRunning = false;
let eventSource = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  // Set default travel date to tomorrow
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  document.getElementById('travelDate').value = tomorrow.toISOString().split('T')[0];

  loadStats();
  loadTasks();
  loadPopularRoutes('tcdd');
  loadSettings();
  initEventStream();

  // Polling fallback
  setInterval(loadStats, 3000);
  setInterval(loadTasks, 5000);
});

// --- Sound Synthesizer (Web Audio API) ---
function playChimeSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc1 = ctx.createOscillator();
    const osc2 = ctx.createOscillator();
    const gain = ctx.createGain();

    osc1.type = 'sine';
    osc1.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
    osc1.frequency.exponentialRampToValueAtTime(880.00, ctx.currentTime + 0.3); // A5

    osc2.type = 'triangle';
    osc2.frequency.setValueAtTime(880.00, ctx.currentTime);
    osc2.frequency.exponentialRampToValueAtTime(1174.66, ctx.currentTime + 0.3); // D6

    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.8);

    osc1.connect(gain);
    osc2.connect(gain);
    gain.connect(ctx.destination);

    osc1.start();
    osc2.start();
    osc1.stop(ctx.currentTime + 0.8);
    osc2.stop(ctx.currentTime + 0.8);
  } catch (e) {
    console.log('Audio not allowed yet by user interaction.');
  }
}

// --- Live Events Stream (SSE) ---
function initEventStream() {
  if (window.EventSource) {
    eventSource = new EventSource('/api/events');
    eventSource.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data);
        handleStreamEvent(payload);
      } catch (err) {}
    };
    eventSource.onerror = () => {
      // Reconnect silently handled by browser
    };
  }
}

function handleStreamEvent(event) {
  const { type, data } = event;
  const timeStr = new Date().toLocaleTimeString();

  if (type === 'seats_found') {
    playChimeSound();
    appendLog(`🚨 [SEAT FOUND] ${data.name}: ${data.seats} seat(s) available!`, 'log-alert');
    loadStats();
    loadTasks();
  } else if (type === 'task_checked') {
    const seats = data.seats || 0;
    if (seats > 0) {
      appendLog(`✔ Checked ${data.name}: ${seats} seat(s) ready.`);
    } else {
      appendLog(`🔍 Checked ${data.name}: Sold Out (0 seats). Monitoring...`);
    }
  } else if (type === 'engine_started') {
    updateEngineState(true);
    appendLog(`🚀 Background Monitoring Engine started.`, 'log-alert');
  } else if (type === 'engine_stopped') {
    updateEngineState(false);
    appendLog(`🛑 Background Monitoring Engine stopped.`);
  }
}

function appendLog(msg, cssClass = '') {
  const container = document.getElementById('logsContainer');
  const div = document.createElement('div');
  div.className = `log-entry ${cssClass}`;
  div.innerHTML = `<span class="log-time">[${new Date().toLocaleTimeString()}]</span> <span>${msg}</span>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function clearLogs() {
  document.getElementById('logsContainer').innerHTML = '';
}

// --- API Calls ---

async function loadStats() {
  try {
    const res = await fetch('/api/stats');
    const data = await res.json();
    document.getElementById('statActiveTasks').textContent = data.active_tasks;
    document.getElementById('statTotalChecks').textContent = data.total_checks;
    document.getElementById('statSeatsFound').textContent = data.seats_found_count;
    updateEngineState(data.engine_running);
  } catch (e) {}
}

function updateEngineState(running) {
  isEngineRunning = running;
  const badge = document.getElementById('engineStatusBadge');
  const text = document.getElementById('engineStatusText');
  const btn = document.getElementById('btnToggleEngine');

  if (running) {
    badge.className = 'status-pill status-active';
    text.textContent = 'Engine Running';
    btn.className = 'btn btn-danger';
    btn.innerHTML = '🛑 Stop Engine';
  } else {
    badge.className = 'status-pill status-paused';
    text.textContent = 'Engine Idle';
    btn.className = 'btn btn-success';
    btn.innerHTML = '▶ Start Engine';
  }
}

async function toggleEngine() {
  const endpoint = isEngineRunning ? '/api/engine/stop' : '/api/engine/start';
  await fetch(endpoint, { method: 'POST' });
  loadStats();
}

async function loadTasks() {
  try {
    const res = await fetch('/api/tasks');
    const tasks = await res.json();
    renderTasks(tasks);
  } catch (e) {}
}

function renderTasks(tasks) {
  const container = document.getElementById('tasksContainer');
  if (!tasks || tasks.length === 0) {
    container.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; padding: 3rem; color: var(--text-muted);">
        No routes being monitored yet. Click <b>+ Add Route</b> or <b>Run Live Cancellation Test</b> to start!
      </div>
    `;
    return;
  }

  container.innerHTML = tasks.map(t => {
    const hasSeats = t.last_found_seats > 0;
    const cardClass = hasSeats ? 'task-card has-seats' : 'task-card';
    const transportClass = t.transport_type === 'flight' ? 'flight' : (t.transport_type === 'bus' ? 'bus' : '');
    
    let seatDisplay = `<span style="color: var(--text-muted);">No seats currently (0)</span>`;
    if (hasSeats) {
      seatDisplay = `<span class="seat-number-badge">${t.last_found_seats} Seat(s) Available! 🎉</span>`;
    }

    const bookingBtn = t.last_service_info && t.last_service_info.booking_url ? `
      <a href="${t.last_service_info.booking_url}" target="_blank" class="btn btn-sm btn-success">
        Book Now ➔
      </a>
    ` : '';

    return `
      <div class="${cardClass}" id="task-card-${t.id}">
        <div>
          <div class="card-top">
            <span class="transport-tag ${transportClass}">${t.transport_type}</span>
            <span style="font-size: 0.8rem; color: var(--text-muted);">Every ${t.check_interval_seconds}s</span>
          </div>
          <div class="route-title">
            ${t.origin} ➔ ${t.destination}
          </div>
          <div class="task-meta">
            <span>📅 ${t.date}</span>
            ${t.time_filter ? `<span>⏰ ${t.time_filter}</span>` : ''}
            <span>🔔 ${t.notification_channels.join(', ')}</span>
          </div>
          <div class="seat-status-box ${hasSeats ? 'found' : ''}">
            ${seatDisplay}
          </div>
        </div>
        <div class="card-actions">
          <div style="display: flex; gap: 0.4rem;">
            <button class="btn btn-sm btn-secondary" onclick="checkTaskNow('${t.id}')" title="Check Now">⚡ Check</button>
            <button class="btn btn-sm btn-secondary" onclick="toggleTaskPause('${t.id}', '${t.status}')">
              ${t.status === 'active' ? '⏸' : '▶'}
            </button>
            <button class="btn btn-sm btn-danger" onclick="deleteTask('${t.id}')" title="Delete">🗑</button>
          </div>
          ${bookingBtn}
        </div>
      </div>
    `;
  }).join('');
}

async function checkTaskNow(taskId) {
  appendLog(`⚡ Manual check triggered for task ${taskId}...`);
  await fetch(`/api/tasks/${taskId}/check`, { method: 'POST' });
  loadTasks();
  loadStats();
}

async function toggleTaskPause(taskId, currentStatus) {
  const action = currentStatus === 'active' ? 'pause' : 'resume';
  await fetch(`/api/tasks/${taskId}/${action}`, { method: 'POST' });
  loadTasks();
}

async function deleteTask(taskId) {
  if (confirm('Are you sure you want to stop tracking this route?')) {
    await fetch(`/api/tasks/${taskId}`, { method: 'DELETE' });
    loadTasks();
    loadStats();
  }
}

async function triggerInstantDemo() {
  appendLog(`🧪 Starting instant live seat cancellation demo...`, 'log-alert');
  const res = await fetch('/api/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      transport_type: 'simulation',
      origin: 'İstanbul(Söğütlüçeşme)',
      destination: 'Ankara Gar',
      date: new Date(Date.now() + 86400000).toISOString().split('T')[0],
      check_interval_seconds: 4,
      notification_channels: ['desktop']
    })
  });
  const newTask = await res.json();
  // Ensure engine is running
  if (!isEngineRunning) {
    await toggleEngine();
  }
  loadTasks();
  loadStats();
}

// --- Modals & Tabs ---

function openNewTaskModal() {
  document.getElementById('modalNewTask').classList.add('open');
}

function openSettingsModal() {
  loadSettings();
  document.getElementById('modalSettings').classList.add('open');
}

function closeModal(id) {
  document.getElementById(id).classList.remove('open');
}

function switchTransportTab(type) {
  currentTransport = type;
  document.getElementById('taskTransportType').value = type;
  
  document.querySelectorAll('#modalNewTask .tab-btn').forEach(btn => {
    btn.classList.remove('active');
  });
  event.target.classList.add('active');

  loadPopularRoutes(type);
}

async function loadPopularRoutes(type) {
  const select = document.getElementById('quickRouteSelect');
  select.innerHTML = '<option value="">-- Choose a standard route or type custom below --</option>';
  try {
    const res = await fetch(`/api/popular-routes?transport=${type}`);
    const routes = await res.json();
    routes.forEach(r => {
      const opt = document.createElement('option');
      opt.value = `${r.origin}|||${r.destination}`;
      opt.textContent = r.label || `${r.origin} ➔ ${r.destination}`;
      select.appendChild(opt);
    });
  } catch (e) {}
}

function applyQuickRoute(val) {
  if (!val) return;
  const [origin, dest] = val.split('|||');
  document.getElementById('originInput').value = origin;
  document.getElementById('destInput').value = dest;
}

async function handleCreateTask(e) {
  e.preventDefault();
  const channels = Array.from(document.querySelectorAll('#newTaskForm input[name="ch"]:checked')).map(c => c.value);
  
  const payload = {
    transport_type: document.getElementById('taskTransportType').value,
    origin: document.getElementById('originInput').value,
    destination: document.getElementById('destInput').value,
    date: document.getElementById('travelDate').value,
    time_filter: document.getElementById('timeFilter').value || null,
    check_interval_seconds: parseInt(document.getElementById('checkInterval').value) || 30,
    seat_class: document.getElementById('seatClass').value,
    notification_channels: channels
  };

  await fetch('/api/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  closeModal('modalNewTask');
  loadTasks();
  loadStats();
  // If engine is not running, start it
  if (!isEngineRunning) {
    toggleEngine();
  }
}

// --- Settings ---

async function loadSettings() {
  try {
    const res = await fetch('/api/config');
    const cfg = await res.json();

    document.getElementById('cfgTelegramToken').value = cfg.telegram.bot_token || '';
    document.getElementById('cfgTelegramChatId').value = cfg.telegram.chat_id || '';
    document.getElementById('cfgTelegramEnabled').checked = !!cfg.telegram.enabled;

    document.getElementById('cfgDiscordUrl').value = cfg.discord.webhook_url || '';
    document.getElementById('cfgDiscordEnabled').checked = !!cfg.discord.enabled;

    document.getElementById('cfgDesktopEnabled').checked = !!cfg.desktop.enabled;
    document.getElementById('cfgSoundEnabled').checked = !!cfg.desktop.sound_enabled;

    document.getElementById('cfgSmtpHost').value = cfg.email.smtp_host || 'smtp.gmail.com';
    document.getElementById('cfgSmtpPort').value = cfg.email.smtp_port || 587;
    document.getElementById('cfgSmtpUser').value = cfg.email.username || '';
    document.getElementById('cfgSmtpPass').value = cfg.email.password || '';
    document.getElementById('cfgSmtpRecipient').value = cfg.email.recipient_email || '';
    document.getElementById('cfgEmailEnabled').checked = !!cfg.email.enabled;
  } catch (e) {}
}

async function handleSaveSettings(e) {
  e.preventDefault();
  const payload = {
    telegram: {
      enabled: document.getElementById('cfgTelegramEnabled').checked,
      bot_token: document.getElementById('cfgTelegramToken').value,
      chat_id: document.getElementById('cfgTelegramChatId').value
    },
    discord: {
      enabled: document.getElementById('cfgDiscordEnabled').checked,
      webhook_url: document.getElementById('cfgDiscordUrl').value
    },
    desktop: {
      enabled: document.getElementById('cfgDesktopEnabled').checked,
      sound_enabled: document.getElementById('cfgSoundEnabled').checked
    },
    email: {
      enabled: document.getElementById('cfgEmailEnabled').checked,
      smtp_host: document.getElementById('cfgSmtpHost').value,
      smtp_port: parseInt(document.getElementById('cfgSmtpPort').value) || 587,
      username: document.getElementById('cfgSmtpUser').value,
      password: document.getElementById('cfgSmtpPass').value,
      recipient_email: document.getElementById('cfgSmtpRecipient').value,
      use_tls: true
    }
  };

  await fetch('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  alert('Settings saved successfully!');
  closeModal('modalSettings');
}

async function testNotification(channel) {
  const res = await fetch('/api/test-notify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ channel })
  });
  const data = await res.json();
  if (data.success) {
    alert(`✔ Test notification for '${channel}' sent successfully!`);
  } else {
    alert(`✖ Test notification failed for '${channel}'. Please check credentials.`);
  }
}
