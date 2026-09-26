// ─── State config ─────────────────────────────────────────────────────────────

const STATES = {
    sleeping: {
        icon: '💤',
        text: 'Sleeping',
        dotColor: 'var(--col-sleeping)',
        dotGlow: 'none',
        pillClass: '',
        waveClass: '',
    },
    wakeword: {
        icon: '⚡',
        text: 'Wake Word!',
        dotColor: 'var(--col-wakeword)',
        dotGlow: '0 0 12px var(--col-wakeword)',
        pillClass: 'wakeword',
        waveClass: 'wakeword',
    },
    listening: {
        icon: '🎙️',
        text: 'Listening',
        dotColor: 'var(--col-listening)',
        dotGlow: '0 0 12px var(--col-listening)',
        pillClass: 'listening',
        waveClass: 'listening',
    },
    thinking: {
        icon: '🤖',
        text: 'Thinking',
        dotColor: 'var(--col-thinking)',
        dotGlow: '0 0 12px var(--col-thinking)',
        pillClass: 'thinking',
        waveClass: 'thinking',
    },
    speaking: {
        icon: '🔊',
        text: 'Speaking',
        dotColor: 'var(--col-speaking)',
        dotGlow: '0 0 12px var(--col-speaking)',
        pillClass: 'speaking',
        waveClass: 'speaking',
    },
};

// ─── DOM refs ─────────────────────────────────────────────────────────────────

const $bars        = document.getElementById('bars');
const $waveGlow    = document.getElementById('waveGlow');
const $pill        = document.getElementById('statusPill');
const $icon        = document.getElementById('statusIcon');
const $text        = document.getElementById('statusText');
const $logoDot     = document.getElementById('logoDot');
const $connInd     = document.getElementById('connIndicator');
const $controlBtn  = document.getElementById('controlBtn');
const $btnText     = document.getElementById('btnText');
const $btnIcon     = document.getElementById('btnIcon');
const $modeSelect  = document.getElementById('modeSelect');
const $modeBadge   = document.getElementById('modeBadge');
const $modeHint    = document.getElementById('modeHint');

// ─── Waveform builder ─────────────────────────────────────────────────────────

const BAR_COUNT = 32;

(function buildBars() {
    for (let i = 0; i < BAR_COUNT; i++) {
        const bar = document.createElement('div');
        bar.className = 'bar';

        // Vary height so bars have different max travel
        const h = 14 + Math.floor(Math.random() * 38);   // 14–52 px
        bar.style.height = `${h}px`;

        // Unique animation duration + a negative delay so they start mid-cycle
        const dur   = (0.65 + Math.random() * 0.85).toFixed(2);
        const delay = (-Math.random() * 1.2).toFixed(2);
        bar.style.setProperty('--dur',   `${dur}s`);
        bar.style.setProperty('--delay', `${delay}s`);

        $bars.appendChild(bar);
    }
})();

// ─── State updater ────────────────────────────────────────────────────────────

function applyState(stateName) {
    const s = STATES[stateName] || STATES.sleeping;

    // Logo dot
    $logoDot.style.background  = s.dotColor;
    $logoDot.style.boxShadow   = s.dotGlow;

    // Waveform bars
    $bars.className = 'bars' + (s.waveClass ? ' ' + s.waveClass : '');

    // Waveform glow bloom
    $waveGlow.className = 'waveform-glow' + (s.waveClass ? ' ' + s.waveClass : '');

    // Status pill
    $pill.className = 'status-pill' + (s.pillClass ? ' ' + s.pillClass : '');
    $icon.textContent = s.icon;
    $text.textContent = s.text;
}

// Apply sleeping state on load
applyState('sleeping');

// ─── WebSocket ────────────────────────────────────────────────────────────────

let ws = null;

function connectWS() {
    ws = new WebSocket('ws://localhost:8000/ws');

    ws.onopen = () => {
        $connInd.classList.add('connected');
        $connInd.title = 'Connected';
    };

    ws.onmessage = (e) => {
        applyState(e.data.trim());
    };

    ws.onclose = () => {
        $connInd.classList.remove('connected');
        $connInd.title = 'Disconnected';
        // Auto-reconnect after 2 s
        setTimeout(connectWS, 2000);
    };

    ws.onerror = () => ws.close();
}

connectWS();

// ─── Mode switcher ────────────────────────────────────────────────────────────

function applyModeUI(mode) {
    const isOffline = (mode === 'offline');
    if ($modeSelect) $modeSelect.value = isOffline ? 'offline' : 'hybrid';
    if ($modeBadge) {
        $modeBadge.textContent = isOffline ? 'Offline' : 'Hybrid';
        $modeBadge.className = 'mode-badge' + (isOffline ? ' offline' : '');
    }
    if ($modeHint) {
        $modeHint.textContent = isOffline
            ? '100% local Ollama (lfm2.5) for orchestrator and agents'
            : 'Groq primary with 15s timeout fallback to Ollama';
    }
}

async function changeModelMode(newMode) {
    applyModeUI(newMode);
    try {
        const res = await fetch('/mode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: newMode }),
        });
        const data = await res.json();
        if (data.mode) {
            applyModeUI(data.mode);
        }
    } catch (err) {
        console.error('Failed to change mode:', err);
    }
}

// ─── Sync running state on load ───────────────────────────────────────────────

(async function syncStatus() {
    try {
        const res  = await fetch('/status');
        const data = await res.json();
        if (data.running) setButtonRunning(true);
        applyState(data.state);
        if (data.mode) applyModeUI(data.mode);
    } catch (_) { /* server not up yet */ }
})();

// ─── Start / Stop ─────────────────────────────────────────────────────────────

let isRunning = false;

function setButtonRunning(running) {
    isRunning = running;
    if (running) {
        $controlBtn.classList.add('running');
        $btnIcon.textContent = '■';
        $btnText.textContent = 'Stop';
    } else {
        $controlBtn.classList.remove('running');
        $btnIcon.textContent = '▶';
        $btnText.textContent = 'Start';
        applyState('sleeping');
    }
}

async function toggleSystem() {
    $controlBtn.disabled = true;

    try {
        if (!isRunning) {
            const res  = await fetch('/start', { method: 'POST' });
            const data = await res.json();
            if (data.status !== 'already_running') setButtonRunning(true);
        } else {
            await fetch('/stop', { method: 'POST' });
            setButtonRunning(false);
        }
    } catch (err) {
        console.error('Control error:', err);
    } finally {
        $controlBtn.disabled = false;
    }
}
