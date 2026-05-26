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

// --- Presets ---
document.getElementById('savePresetBtn')?.addEventListener('click', () => {
    const presets = [1, 2, 3].map(i => ({
        enabled: document.getElementById('enable' + i).checked,
        startRow: document.getElementById('startRow' + i).value,
        endRow: document.getElementById('endRow' + i).value,
        tempMin: document.getElementById('tempMin' + i).value,
        tempMax: document.getElementById('tempMax' + i).value,
        timePeriod: document.getElementById('timePeriod' + i).value,
        uValue: document.getElementById('uValue' + i).value,
        scheduleTime: document.getElementById('scheduleTime' + i).value
    }));
    const globalPreset = {
        tabs: presets,
        showBrowser: document.getElementById('showBrowser').checked,
        typingSpeed: document.getElementById('typingSpeed').value
    };
    localStorage.setItem('afs_preset_v2', JSON.stringify(globalPreset));
    alert('บันทึกการตั้งค่าทั้งหมดเรียบร้อยแล้ว');
});

document.getElementById('loadPresetBtn')?.addEventListener('click', () => {
    const data = localStorage.getItem('afs_preset_v2');
    if(data) {
        const globalPreset = JSON.parse(data);
        if (globalPreset.tabs) {
            globalPreset.tabs.forEach((preset, idx) => {
                const i = idx + 1;
                document.getElementById('enable' + i).checked = preset.enabled ?? (i === 1);
                document.getElementById('startRow' + i).value = preset.startRow || 1;
                document.getElementById('endRow' + i).value = preset.endRow || 39;
                document.getElementById('tempMin' + i).value = preset.tempMin || 35.9;
                document.getElementById('tempMax' + i).value = preset.tempMax || 36.1;
                document.getElementById('timePeriod' + i).value = preset.timePeriod || 'morning';
                document.getElementById('uValue' + i).value = preset.uValue || 'skip';
                document.getElementById('scheduleTime' + i).value = preset.scheduleTime || '';
            });
        }
        document.getElementById('showBrowser').checked = globalPreset.showBrowser ?? true;
        if (globalPreset.typingSpeed) {
            document.getElementById('typingSpeed').value = globalPreset.typingSpeed;
        }
        alert('โหลดการตั้งค่าทั้งหมดเรียบร้อยแล้ว');
    } else {
        alert('ไม่พบการตั้งค่าที่บันทึกไว้');
    }
});

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
        if (taskQueue.length === 0 && pendingSchedules.length === 0) {
            stopBtn.classList.add('hidden');
            if(pauseBtn) pauseBtn.classList.add('hidden');
            submitBtn.classList.remove('hidden');
            submitBtn.disabled = false;
            btnText.textContent = 'Start Automation';
            spinner.classList.add('hidden');
            if (pulseDot) pulseDot.classList.add('hidden');
        } else {
            // If there are still schedules waiting but queue is empty
            if (taskQueue.length === 0) {
                statusTitle.textContent = 'รอกำหนดเวลาถัดไป...';
                statusTitle.style.color = '#eab308';
                statusMessage.textContent = `มีงานรอทำงานอีก ${pendingSchedules.length} งาน`;
                if (pulseDot) pulseDot.classList.remove('hidden');
                submitBtn.classList.add('hidden');
                stopBtn.classList.remove('hidden');
                stopBtn.disabled = false;
                stopBtn.querySelector('.btn-text').textContent = 'Cancel Schedules';
                if(pauseBtn) pauseBtn.classList.add('hidden');
            }
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
                    if (taskQueue.length === 0 && pendingSchedules.length === 0) {
                        successIcon.classList.remove('hidden');
                        statusTitle.textContent = 'เสร็จสิ้นทั้งหมด!';
                        statusTitle.style.color = '#10b981';
                        statusMessage.textContent = 'กระบวนการทำงานจบลงแล้ว';
                    }
                    playBeep(false);
                } else {
                    if (taskQueue.length === 0 && pendingSchedules.length === 0) {
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
        
        if (taskQueue.length === 0 && pendingSchedules.length === 0) {
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
    let anyScheduled = false;
    let anyImmediate = false;
    let scheduledTimes = [];
    
    for(let i = 1; i <= 3; i++) {
        if(document.getElementById('enable' + i).checked) {
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
            
            const scheduleTime = document.getElementById('scheduleTime' + i).value;
            if(scheduleTime) {
                pendingSchedules.push({
                    task: task,
                    targetMs: calculateTargetMs(scheduleTime),
                    scheduleTime: scheduleTime
                });
                anyScheduled = true;
                scheduledTimes.push(scheduleTime);
            } else {
                taskQueue.push(task);
                anyImmediate = true;
            }
        }
    }
    
    if (!anyScheduled && !anyImmediate) {
        alert("กรุณาเปิดใช้งานอย่างน้อย 1 ช่วงเวลา");
        return;
    }
    
    const submitBtn = document.getElementById('submitBtn');
    const stopBtn = document.getElementById('stopBtn');
    const statusBox = document.getElementById('statusBox');
    const statusTitle = document.getElementById('statusTitle');
    const statusMessage = document.getElementById('statusMessage');
    const pulseDot = document.querySelector('.pulse-dot');
    
    if (anyScheduled) {
        masterTimer = setInterval(() => {
            const nowMs = Date.now();
            let tasksToRun = [];
            
            pendingSchedules = pendingSchedules.filter(s => {
                if (nowMs >= s.targetMs) {
                    tasksToRun.push(s.task);
                    return false; // remove
                }
                return true; // keep
            });
            
            if (tasksToRun.length > 0) {
                tasksToRun.forEach(t => taskQueue.push(t));
                runNextTask();
            }
            
            // UI Update for countdown if waiting
            if (pendingSchedules.length > 0 && taskQueue.length === 0 && !isRunning) {
                const nearest = [...pendingSchedules].sort((a,b) => a.targetMs - b.targetMs)[0];
                const diffSecs = Math.floor((nearest.targetMs - nowMs) / 1000);
                const h = Math.floor(diffSecs / 3600);
                const m = Math.floor((diffSecs % 3600) / 60);
                const s = diffSecs % 60;
                const timeStr = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
                statusMessage.textContent = `คิวถัดไป (${nearest.task.label}) เริ่มในอีก ${timeStr}`;
            }
        }, 1000);
    }
    
    if (anyScheduled && !anyImmediate) {
        statusBox.classList.remove('hidden');
        statusTitle.textContent = 'กำลังรอเวลา...';
        statusTitle.style.color = '#eab308';
        statusMessage.textContent = `ระบบจะทำงานเวลา: ${scheduledTimes.join(', ')}`;
        if (pulseDot) pulseDot.classList.remove('hidden');
        
        submitBtn.classList.add('hidden');
        stopBtn.classList.remove('hidden');
        stopBtn.disabled = false;
        stopBtn.querySelector('.btn-text').textContent = 'Cancel Schedules';
    } else {
        runNextTask();
    }
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
