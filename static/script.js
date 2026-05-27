// --- Live Clock Logic ---
function updateClock() {
    const timeEl = document.getElementById('liveTime');
    const dateEl = document.getElementById('liveDate');
    if (!timeEl || !dateEl) return;
    
    const now = new Date();
    const timeStr = now.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const dateStr = now.toLocaleDateString('th-TH', { year: 'numeric', month: 'short', day: 'numeric', weekday: 'short' });
    
    timeEl.textContent = timeStr;
    dateEl.textContent = dateStr;
}
setInterval(updateClock, 1000);
updateClock(); 
// -----------------------

// --- Audio ---
function playBeep(isError=false) {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    
    osc.type = isError ? 'sawtooth' : 'sine';
    osc.frequency.setValueAtTime(isError ? 300 : 800, ctx.currentTime);
    if(isError) {
        osc.frequency.exponentialRampToValueAtTime(100, ctx.currentTime + 0.5);
    } else {
        osc.frequency.setValueAtTime(1200, ctx.currentTime + 0.1);
    }
    
    gain.gain.setValueAtTime(0.1, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5);
    
    osc.start();
    osc.stop(ctx.currentTime + 0.5);
}

// --- Tabs Logic ---
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(btn.dataset.tab).classList.add('active');
    });
});

// --- Presets (JSON CRUD) ---
let serverPresets = {};

async function fetchPresets() {
    try {
        const res = await fetch('/api/presets');
        const data = await res.json();
        serverPresets = data.presets || {};
        updatePresetDropdowns();
    } catch (err) {
        console.error('Failed to fetch presets', err);
    }
}

async function fetchActiveState() {
    try {
        const res = await fetch('/api/active_state');
        const data = await res.json();
        if (data.tabs) {
            data.tabs.forEach((tab, idx) => {
                const i = idx + 1;
                const enableEl = document.getElementById('enable' + i);
                if (enableEl) enableEl.checked = tab.enabled ?? (i === 1);
                
                const fields = ['startRow', 'endRow', 'tempMin', 'tempMax', 'timePeriod', 'uValue', 'scheduleTime'];
                fields.forEach(f => {
                    const el = document.getElementById(f + i);
                    if (el && tab[f] !== undefined && tab[f] !== null) {
                        el.value = tab[f];
                    }
                });
            });
            const sbEl = document.getElementById('showBrowser');
            if (sbEl) sbEl.checked = data.showBrowser ?? false;
            
            const tsEl = document.getElementById('typingSpeed');
            if (tsEl && data.typingSpeed) {
                tsEl.value = data.typingSpeed;
            }
        } else {
            // Fallback: If no active state saved yet, try loading 'Default' preset if it exists
            if (serverPresets && serverPresets["Default"]) {
                for (let i = 1; i <= 3; i++) {
                    loadPresetToTab(i, "Default");
                }
            }
        }
    } catch (err) {
        console.error('Failed to fetch active state', err);
    }
}

function updatePresetDropdowns() {
    for (let i = 1; i <= 3; i++) {
        const selector = document.getElementById('presetSelector' + i);
        if (!selector) continue;
        
        const currentValue = selector.value;
        selector.innerHTML = '<option value="">-- เลือกโปรไฟล์ --</option>';
        
        Object.keys(serverPresets).forEach(name => {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            selector.appendChild(opt);
        });
        
        if (serverPresets[currentValue]) {
            selector.value = currentValue;
        }
    }
}

function loadPresetToTab(tabIndex, presetName) {
    const preset = serverPresets[presetName];
    if (!preset) return;
    
    // Support loading old format presets (which contained a 'tabs' array)
    const isOldFormat = preset.tabs !== undefined && Array.isArray(preset.tabs);
    const sourceData = isOldFormat ? preset.tabs[tabIndex - 1] : preset;
    
    if (!sourceData) return;
    
    const fields = ['startRow', 'endRow', 'tempMin', 'tempMax', 'timePeriod', 'uValue', 'scheduleTime'];
    fields.forEach(f => {
        const el = document.getElementById(f + tabIndex);
        if (el && sourceData[f] !== undefined && sourceData[f] !== null) {
            el.value = sourceData[f];
        }
    });
}

function getTabValues(tabIndex) {
    return {
        startRow: document.getElementById('startRow' + tabIndex).value,
        endRow: document.getElementById('endRow' + tabIndex).value,
        tempMin: document.getElementById('tempMin' + tabIndex).value,
        tempMax: document.getElementById('tempMax' + tabIndex).value,
        timePeriod: document.getElementById('timePeriod' + tabIndex).value,
        uValue: document.getElementById('uValue' + tabIndex).value,
        scheduleTime: document.getElementById('scheduleTime' + tabIndex).value
    };
}

function getFormValues() {
    const tabs = [1, 2, 3].map(i => ({
        enabled: document.getElementById('enable' + i).checked,
        ...getTabValues(i)
    }));
    return {
        tabs: tabs,
        showBrowser: document.getElementById('showBrowser').checked,
        typingSpeed: document.getElementById('typingSpeed').value
    };
}

async function saveTabPreset(tabIndex, presetName) {
    const presetData = getTabValues(tabIndex);
    try {
        const res = await fetch('/api/presets', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ preset_name: presetName, preset_data: presetData })
        });
        const data = await res.json();
        
        if(data.success) {
            await fetchPresets();
            alert(data.message);
            document.getElementById('presetSelector' + tabIndex).value = presetName;
        } else {
            alert('เกิดข้อผิดพลาด: ' + data.message);
        }
    } catch (err) {
        alert('เกิดข้อผิดพลาดในการเชื่อมต่อ');
        console.error(err);
    }
}

async function saveActiveState() {
    const stateData = getFormValues();
    try {
        const res = await fetch('/api/active_state', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(stateData)
        });
        const data = await res.json();
        if (data.success) {
            alert(data.message);
        } else {
            alert('เกิดข้อผิดพลาด: ' + data.message);
        }
    } catch (err) {
        alert('เกิดข้อผิดพลาดในการเชื่อมต่อ');
        console.error(err);
    }
}

// Add event listeners for per-tab preset controls
for (let i = 1; i <= 3; i++) {
    document.getElementById('loadPresetBtn' + i)?.addEventListener('click', () => {
        const presetName = document.getElementById('presetSelector' + i).value;
        if (presetName) {
            loadPresetToTab(i, presetName);
        } else {
            alert("กรุณาเลือกโปรไฟล์ที่ต้องการโหลด");
        }
    });

    document.getElementById('savePresetBtn' + i)?.addEventListener('click', () => {
        const newName = prompt(`ตั้งชื่อโปรไฟล์สำหรับช่วงที่ ${i}:`);
        if (newName && newName.trim()) {
            saveTabPreset(i, newName.trim());
        }
    });

    document.getElementById('deletePresetBtn' + i)?.addEventListener('click', async () => {
        const selector = document.getElementById('presetSelector' + i);
        const currentName = selector.value;
        if (!currentName) {
            alert("กรุณาเลือกโปรไฟล์ที่ต้องการลบ");
            return;
        }
        
        if (confirm(`คุณแน่ใจหรือไม่ว่าต้องการลบโปรไฟล์ '${currentName}'?`)) {
            try {
                const res = await fetch(`/api/presets/${currentName}`, { method: 'DELETE' });
                const data = await res.json();
                if (data.success) {
                    alert(data.message);
                    await fetchPresets();
                } else {
                    alert('เกิดข้อผิดพลาด: ' + data.message);
                }
            } catch (err) {
                console.error(err);
            }
        }
    });
}

document.getElementById('saveActiveStateBtn')?.addEventListener('click', () => {
    saveActiveState();
});

window.addEventListener('DOMContentLoaded', async () => {
    await fetchPresets();
    await fetchActiveState();
    pollBackgroundLogs(); // Start polling immediately on load
});

// --- Background Logs Polling ---
let lastBgLogIndex = 0;
async function pollBackgroundLogs() {
    try {
        const res = await fetch(`/api/bg_logs?since=${lastBgLogIndex}`);
        if (!res.ok) return;
        const data = await res.json();
        
        if (data.logs && data.logs.length > 0) {
            const logContainer = document.getElementById('logContainer');
            if (logContainer) {
                data.logs.forEach(log => {
                    const logEntry = document.createElement('div');
                    logEntry.style.marginBottom = '4px';
                    
                    if (log.type === 'error') logEntry.style.color = '#ef4444';
                    else if (log.type === 'success') logEntry.style.color = '#10b981';
                    else if (log.type === 'warning') logEntry.style.color = '#eab308';
                    else logEntry.style.color = '#e2e8f0'; // Default text color
                    
                    // Add timestamp if available
                    const timeStr = new Date().toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                    logEntry.textContent = `[${timeStr}] > ${log.message}`;
                    
                    logContainer.appendChild(logEntry);
                });
                // Keep only last 200 logs to prevent memory issues
                while (logContainer.children.length > 200) {
                    logContainer.removeChild(logContainer.firstChild);
                }
                logContainer.scrollTop = logContainer.scrollHeight;
            }
            lastBgLogIndex = data.next_index;
        }
    } catch (e) {
        // Silent error for background polling
    }
}

// Poll every 2 seconds
setInterval(pollBackgroundLogs, 2000);

let scheduleTimers = [];
let taskQueue = [];
let isRunning = false;
let isPaused = false;
let currentEventSource = null;

function runNextTask() {
    if (isRunning || taskQueue.length === 0) return;
    
    const task = taskQueue.shift();
    isRunning = true;
    isPaused = false;
    
    // UI Elements
    const submitBtn = document.getElementById('submitBtn');
    const stopBtn = document.getElementById('stopBtn');
    const pauseBtn = document.getElementById('pauseBtn');
    const btnText = submitBtn.querySelector('.btn-text');
    const spinner = submitBtn.querySelector('.spinner');
    const statusBox = document.getElementById('statusBox');
    const statusTitle = document.getElementById('statusTitle');
    const statusMessage = document.getElementById('statusMessage');
    const successIcon = document.querySelector('.success-icon');
    const errorIcon = document.querySelector('.error-icon');
    const pulseDot = document.querySelector('.pulse-dot');
    const logContainer = document.getElementById('logContainer');
    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    
    submitBtn.classList.add('hidden');
    stopBtn.classList.remove('hidden');
    if(pauseBtn) {
        pauseBtn.classList.remove('hidden');
        pauseBtn.disabled = false;
        pauseBtn.querySelector('.btn-text').textContent = 'Pause';
        pauseBtn.style.background = '#f59e0b';
    }
    stopBtn.disabled = false;
    stopBtn.querySelector('.btn-text').textContent = 'Stop';
    
    statusBox.classList.remove('hidden');
    successIcon.classList.add('hidden');
    errorIcon.classList.add('hidden');
    if (pulseDot) pulseDot.classList.remove('hidden');
    
    if(progressContainer) progressContainer.classList.remove('hidden');
    if(progressBar) progressBar.style.width = '0%';
    if(progressText) progressText.textContent = '0%';
    
    logContainer.style.display = 'block';
    logContainer.innerHTML += `<div>เริ่มทำงานช่วง: ${task.label}...</div>`;
    
    statusTitle.textContent = `กำลังทำงาน (${task.label})`;
    statusMessage.textContent = 'คิวงานถัดไป: ' + taskQueue.length;
    statusTitle.style.color = '#3b82f6';
    
    const url = `/api/start?startRow=${task.startRow}&endRow=${task.endRow}&tempMin=${task.tempMin}&tempMax=${task.tempMax}&timePeriod=${task.timePeriod}&showBrowser=${task.showBrowser}&uValue=${task.uValue}&speed=${task.speed}`;
    currentEventSource = new EventSource(url);
    
    function resetButtons() {
        if (taskQueue.length === 0) {
            stopBtn.classList.add('hidden');
            if(pauseBtn) pauseBtn.classList.add('hidden');
            submitBtn.classList.remove('hidden');
            submitBtn.disabled = false;
            btnText.textContent = 'Start Automation';
            spinner.classList.add('hidden');
            if (pulseDot) pulseDot.classList.add('hidden');
        }
    }
    
    currentEventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'progress') {
                if(data.total > 0 && progressBar && progressText) {
                    const pct = Math.round((data.current / data.total) * 100);
                    progressBar.style.width = pct + '%';
                    progressText.textContent = pct + '%';
                }
                if (!data.message) return;
            }
            
            if (data.message) {
                const logEntry = document.createElement('div');
                logEntry.style.marginBottom = '4px';
                
                if (data.type === 'error') logEntry.style.color = '#ef4444';
                else if (data.type === 'success') logEntry.style.color = '#10b981';
                else if (data.type === 'warning') logEntry.style.color = '#eab308';
                
                logEntry.textContent = `> ${data.message}`;
                logContainer.appendChild(logEntry);
                logContainer.scrollTop = logContainer.scrollHeight;
            }
            
            if (data.type === 'success' || data.type === 'error') {
                currentEventSource.close();
                isRunning = false;
                
                if (data.type === 'success') {
                    if (taskQueue.length === 0) {
                        successIcon.classList.remove('hidden');
                        statusTitle.textContent = 'เสร็จสิ้นทั้งหมด!';
                        statusTitle.style.color = '#10b981';
                        statusMessage.textContent = 'กระบวนการทำงานจบลงแล้ว';
                    }
                    playBeep(false);
                } else {
                    if (taskQueue.length === 0) {
                        errorIcon.classList.remove('hidden');
                        statusTitle.textContent = 'เกิดข้อผิดพลาด';
                        statusTitle.style.color = '#ef4444';
                        statusMessage.textContent = 'ระบบหยุดทำงาน';
                    }
                    playBeep(true);
                }
                
                resetButtons();
                runNextTask(); // Run next in queue if any
            }
        } catch (e) {
            console.error('Error parsing SSE data', e);
        }
    };
    
    currentEventSource.onerror = function(err) {
        console.error('SSE Error', err);
        currentEventSource.close();
        isRunning = false;
        
        if (taskQueue.length === 0) {
            errorIcon.classList.remove('hidden');
            statusTitle.textContent = 'ขาดการเชื่อมต่อ';
            statusTitle.style.color = '#ef4444';
            statusMessage.textContent = 'ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ได้';
        }
        resetButtons();
        playBeep(true);
        runNextTask();
    };
}

let pendingSchedules = [];
let masterTimer = null;

function calculateTargetMs(scheduleTime) {
    const now = new Date();
    const [hours, minutes] = scheduleTime.split(':').map(Number);
    const target = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hours, minutes, 0);
    if (target < now) {
        target.setDate(target.getDate() + 1);
    }
    return target.getTime();
}

document.getElementById('automationForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    // Clear previous timers and queue
    if (masterTimer) clearInterval(masterTimer);
    pendingSchedules = [];
    taskQueue = [];
    
    const showBrowser = document.getElementById('showBrowser').checked;
    let anyImmediate = false;
    
    const activeTabBtn = document.querySelector('.tab-btn.active');
    const activeTabId = activeTabBtn ? activeTabBtn.getAttribute('data-tab') : 'tab-1';
    const i = parseInt(activeTabId.split('-')[1]);
    
    const task = {
        label: 'ช่วงที่ ' + i,
        startRow: document.getElementById('startRow' + i).value,
        endRow: document.getElementById('endRow' + i).value,
        tempMin: document.getElementById('tempMin' + i).value,
        tempMax: document.getElementById('tempMax' + i).value,
        timePeriod: document.getElementById('timePeriod' + i).value,
        uValue: document.getElementById('uValue' + i).value,
        showBrowser: showBrowser,
        speed: document.getElementById('typingSpeed').value
    };
    
    taskQueue.push(task);
    anyImmediate = true;
    
    const submitBtn = document.getElementById('submitBtn');
    const stopBtn = document.getElementById('stopBtn');
    const statusBox = document.getElementById('statusBox');
    const statusTitle = document.getElementById('statusTitle');
    const statusMessage = document.getElementById('statusMessage');
    const pulseDot = document.querySelector('.pulse-dot');
    
    runNextTask();
});

document.getElementById('stopBtn').addEventListener('click', function() {
    this.disabled = true;
    const pauseBtn = document.getElementById('pauseBtn');
    if(pauseBtn) pauseBtn.disabled = true;
    this.querySelector('.btn-text').textContent = 'กำลังยกเลิก...';
    
    // Clear all pending schedules and queue
    if (masterTimer) clearInterval(masterTimer);
    pendingSchedules = [];
    taskQueue = [];
    
    if (isRunning && currentEventSource) {
        fetch('/api/stop', { method: 'POST' });
    } else {
        // If it was just waiting, restore UI immediately
        const submitBtn = document.getElementById('submitBtn');
        const statusTitle = document.getElementById('statusTitle');
        const statusMessage = document.getElementById('statusMessage');
        const pulseDot = document.querySelector('.pulse-dot');
        
        this.classList.add('hidden');
        submitBtn.classList.remove('hidden');
        submitBtn.disabled = false;
        statusTitle.textContent = 'ยกเลิกการทำงาน/รอเวลาแล้ว';
        statusTitle.style.color = '#ef4444';
        statusMessage.textContent = 'รอคำสั่งใหม่';
        if (pulseDot) pulseDot.classList.add('hidden');
    }
});

const pauseBtn = document.getElementById('pauseBtn');
if (pauseBtn) {
    pauseBtn.addEventListener('click', function() {
        if(isPaused) {
            isPaused = false;
            this.querySelector('.btn-text').textContent = 'Pause';
            this.style.background = '#f59e0b';
            document.getElementById('statusTitle').textContent = 'กำลังทำงาน';
            fetch('/api/resume', { method: 'POST' });
        } else {
            isPaused = true;
            this.querySelector('.btn-text').textContent = 'Resume';
            this.style.background = '#10b981';
            document.getElementById('statusTitle').textContent = 'หยุดชั่วคราว';
            fetch('/api/pause', { method: 'POST' });
        }
    });
}

// --- Logout (Clear Cache) ---
document.getElementById('logoutBtn')?.addEventListener('click', function() {
    localStorage.clear();
});

// =============================================
// --- Background Log Polling ---
// Polls /api/bg_logs every 3 seconds and shows
// any logs from the background scheduler in terminal
// =============================================
let bgLogIndex = 0;

function appendBgLog(logData) {
    const logContainer = document.getElementById('logContainer');
    if (!logContainer) return;
    const logEntry = document.createElement('div');
    logEntry.style.marginBottom = '4px';
    if (logData.type === 'error') logEntry.style.color = '#ef4444';
    else if (logData.type === 'success') logEntry.style.color = '#10b981';
    else if (logData.type === 'warning') logEntry.style.color = '#eab308';
    else logEntry.style.color = '#a78bfa';  // purple for background tasks
    logEntry.textContent = `[AUTO] ${logData.message}`;
    logContainer.appendChild(logEntry);
    logContainer.scrollTop = logContainer.scrollHeight;
}

function pollBgLogs() {
    fetch('/api/bg_logs?since=' + bgLogIndex)
        .then(res => res.json())
        .then(data => {
            if (data.logs && data.logs.length > 0) {
                bgLogIndex = data.next_index;
                data.logs.forEach(entry => appendBgLog(entry));
                
                // Update status box if a background job just started/ended
                const lastLog = data.logs[data.logs.length - 1];
                if (lastLog) {
                    const statusTitle = document.getElementById('statusTitle');
                    const statusMessage = document.getElementById('statusMessage');
                    const statusBox = document.getElementById('statusBox');
                    if (lastLog.type === 'success' && !isRunning) {
                        statusBox.classList.remove('hidden');
                        statusTitle.textContent = '✅ Auto เสร็จสิ้น';
                        statusTitle.style.color = '#10b981';
                        statusMessage.textContent = lastLog.message;
                    } else if (lastLog.type === 'error' && !isRunning) {
                        statusBox.classList.remove('hidden');
                        statusTitle.textContent = '❌ Auto เกิดข้อผิดพลาด';
                        statusTitle.style.color = '#ef4444';
                        statusMessage.textContent = lastLog.message;
                    } else if (!isRunning && lastLog.bg_task_start) {
                        statusBox.classList.remove('hidden');
                        statusTitle.textContent = '⚙️ กำลังรันอัตโนมัติเบื้องหลัง...';
                        statusTitle.style.color = '#a78bfa';
                        statusMessage.textContent = lastLog.message;
                    }
                }
            }
        })
        .catch(() => {}); // Silently ignore polling errors
}

// Start polling every 3 seconds
setInterval(pollBgLogs, 3000);
