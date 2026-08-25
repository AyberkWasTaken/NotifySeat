/**
 * NotifySeat Web Application
 * Local Transport Seat & Cancellation Radar
 * Crafted for Ayberk
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
  setInterval(loadTasks, 4000);
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

    gain.gain.setValueAtTime(0.35, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.8);

    osc1.connect(gain);
    osc2.connect(gain);
    gain.connect(ctx.destination);

    osc1.start();
    osc2.start();
    osc1.stop(ctx.currentTime + 0.8);
    osc2.stop(ctx.currentTime + 0.8);
  } catch (e) {
    console.log('Audio requires prior user interaction in this browser.');
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
      // Browser handles reconnect
    };
  }
}

function handleStreamEvent(event) {
  const { type, data } = event;

  if (type === 'seats_found') {
    playChimeSound();
    const msg = data.message || `🚨 ${data.seats} seat(s) found on ${data.name}!`;
    appendLog(msg, 'log-alert');
    loadStats();
    loadTasks();
  } else if (type === 'task_checked') {
    const seats = data.seats || 0;
    if (seats > 0) {
      appendLog(data.message || `✔ Checked ${data.name}: ${seats} seat(s) available.`);
    } else {
      appendLog(data.message || `🔍 Checked ${data.name}: 0 seats available. Monitoring...`);
    }
  } else if (type === 'rate_limit_backoff') {
    const mins = data.minutes || 3;
    appendLog(`🌱 TCDD Güvenlik Dinlenmesi: IP adresinizi korumak için ${mins} dakika mola verildi. Kontroller otomatik devam edecek.`, 'log-alert');
  } else if (type === 'rate_limit_recovered') {
    appendLog(`✔ Güvenlik molası tamamlandı. Bilet kontrolleri normal hızında yeniden başladı.`);
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
    
    // Parse detailed services
    let servicesList = [];
    let bookingUrl = 'https://ebilet.tcddtasimacilik.gov.tr';
    if (t.last_service_info) {
      if (Array.isArray(t.last_service_info.services)) {
        servicesList = t.last_service_info.services;
      } else if (t.last_service_info.service_name) {
        servicesList = [t.last_service_info];
      }
      if (t.last_service_info.booking_url) {
        bookingUrl = t.last_service_info.booking_url;
      }
    }

    let seatDisplay = '';
    if (hasSeats && servicesList.length > 0) {
      seatDisplay = `
        <div style="margin-bottom: 0.5rem;">
          <span class="seat-number-badge">${t.last_found_seats} Seat(s) Available! 🎉</span>
        </div>
        <div style="display: flex; flex-direction: column; gap: 0.35rem;">
          ${servicesList.map(s => {
            const classText = s.class_breakdown ? Object.entries(s.class_breakdown)
              .filter(([_, count]) => count > 0)
              .map(([cls, count]) => `${count} ${cls}`).join(', ') : '';
            return `
              <div style="font-size: 0.85rem; background: rgba(0,0,0,0.25); padding: 0.4rem 0.6rem; border-radius: 6px; border-left: 3px solid var(--accent-green);">
                <b>⏰ ${s.departure_time}</b> - ${s.service_name}: <b>${s.total_available_seats} seat(s)</b>
                ${classText ? `<div style="font-size: 0.75rem; color: #a7f3d0;">(${classText})</div>` : ''}
              </div>
            `;
          }).join('')}
        </div>
      `;
    } else if (hasSeats) {
      seatDisplay = `<span class="seat-number-badge">${t.last_found_seats} Seat(s) Available! 🎉</span>`;
    } else {
      const lastCheckTime = t.last_checked_at ? new Date(t.last_checked_at).toLocaleTimeString() : 'Pending first check';
      seatDisplay = `
        <div style="font-size: 0.85rem; color: var(--text-muted);">
          All trains/trips sold out (0 seats).
          <div style="font-size: 0.75rem; margin-top: 0.2rem;">Last checked at ${lastCheckTime}. Watching for passenger cancellations...</div>
        </div>
      `;
    }

    const bookingBtn = hasSeats ? `
      <a href="${bookingUrl}" target="_blank" class="btn btn-sm btn-success">
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
            <button class="btn btn-sm btn-secondary" onclick="checkTaskNow('${t.id}')" title="Check Now">⚡ Check Now</button>
            <button class="btn btn-sm btn-secondary" onclick="toggleTaskPause('${t.id}', '${t.status}')">
              ${t.status === 'active' ? '⏸ Pause' : '▶ Resume'}
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
  appendLog(`⚡ Triggering immediate live check for task [${taskId}]...`);
  const res = await fetch(`/api/tasks/${taskId}/check`, { method: 'POST' });
  const data = await res.json();
  loadTasks();
  loadStats();
}

async function toggleTaskPause(taskId, currentStatus) {
  const action = currentStatus === 'active' ? 'pause' : 'resume';
  await fetch(`/api/tasks/${taskId}/${action}`, { method: 'POST' });
  loadTasks();
}

async function deleteTask(taskId) {
  if (confirm('Are you sure you want to delete this route tracker?')) {
    await fetch(`/api/tasks/${taskId}`, { method: 'DELETE' });
    loadTasks();
    loadStats();
  }
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
    check_interval_seconds: 90,
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
  
  // If engine is not running, auto-start it
  if (!isEngineRunning) {
    toggleEngine();
  }
}

// --- Settings & Notification Channels ---

async function loadSettings() {
  try {
    const res = await fetch('/api/config');
    const cfg = await res.json();

    // WhatsApp
    const wa = cfg.whatsapp || {};
    const waPhoneEl = document.getElementById('cfgWhatsappPhone');
    const waKeyEl = document.getElementById('cfgWhatsappApiKey');
    const waEnabledEl = document.getElementById('cfgWhatsappEnabled');
    if (waPhoneEl) waPhoneEl.value = wa.phone_number || '';
    if (waKeyEl) waKeyEl.value = wa.apikey || '';
    if (waEnabledEl) waEnabledEl.checked = wa.enabled !== false;

    // Email (Gmail)
    const em = cfg.email || {};
    const emUserEl = document.getElementById('cfgSmtpUser');
    const emPassEl = document.getElementById('cfgSmtpPass');
    const emRecipEl = document.getElementById('cfgSmtpRecipient');
    const emEnabledEl = document.getElementById('cfgEmailEnabled');
    if (emUserEl) emUserEl.value = em.username || '';
    if (emPassEl) emPassEl.value = em.password || '';
    if (emRecipEl) emRecipEl.value = em.recipient_email || '';
    if (emEnabledEl) emEnabledEl.checked = !!em.enabled;

    // Desktop
    const desk = cfg.desktop || {};
    const deskEnabledEl = document.getElementById('cfgDesktopEnabled');
    const soundEnabledEl = document.getElementById('cfgSoundEnabled');
    if (deskEnabledEl) deskEnabledEl.checked = desk.enabled !== false;
    if (soundEnabledEl) soundEnabledEl.checked = desk.sound_enabled !== false;

    // Update Channel Status Pill
    const statusEl = document.getElementById('statChannelsStatus');
    if (statusEl) {
      const active = [];
      if (wa.enabled && wa.phone_number) active.push('WhatsApp');
      if (em.enabled && em.username) active.push('E-posta');
      if (desk.enabled) active.push('Masaüstü');
      statusEl.textContent = active.length > 0 ? active.join(' + ') : 'Pasif (Ayar Yapın)';
    }
  } catch (e) {}
}

async function handleSaveSettings(e) {
  e.preventDefault();
  const gmailUser = document.getElementById('cfgSmtpUser').value.trim();
  const recipient = document.getElementById('cfgSmtpRecipient').value.trim() || gmailUser;

  const payload = {
    whatsapp: {
      enabled: document.getElementById('cfgWhatsappEnabled').checked,
      phone_number: document.getElementById('cfgWhatsappPhone').value.trim(),
      apikey: document.getElementById('cfgWhatsappApiKey').value.trim()
    },
    email: {
      enabled: document.getElementById('cfgEmailEnabled').checked,
      smtp_host: 'smtp.gmail.com',
      smtp_port: 587,
      use_tls: true,
      username: gmailUser,
      password: document.getElementById('cfgSmtpPass').value.trim(),
      sender_email: gmailUser,
      recipient_email: recipient
    },
    desktop: {
      enabled: document.getElementById('cfgDesktopEnabled').checked,
      sound_enabled: document.getElementById('cfgSoundEnabled').checked
    }
  };

  await fetch('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  alert('✔ Bildirim ayarları başarıyla kaydedildi!');
  closeModal('modalSettings');
  loadSettings();
}

async function testNotification(channel) {
  const channelNameTr = channel === 'whatsapp' ? 'WhatsApp' : (channel === 'email' ? 'E-posta' : 'Masaüstü');
  const res = await fetch('/api/test-notify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ channel })
  });
  const data = await res.json();
  if (data.success) {
    alert(`✔ ${channelNameTr} test bildirimi başarıyla gönderildi! Lütfen kontrol edin.`);
  } else {
    alert(`✖ ${channelNameTr} bildirimi gönderilemedi. Lütfen bilgilerinizi (API Key veya Uygulama Şifresi) kontrol edin.`);
  }
}
