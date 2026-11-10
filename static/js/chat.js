/* ══════════════════════════════════════════════
   LSPD - محادثة لحظية (للرتب العليا فقط)
   ══════════════════════════════════════════════ */

const socket = io();
const ME = window.ME;
const OTHER = window.OTHER;

const msgsBox = document.getElementById('msgs');
const inputEl = document.getElementById('input');
const sendBtn = document.getElementById('send');


/* ═══ الانضمام ═══ */

function joinRoom() {
    socket.emit('join', { room: 'general', user: ME, other: OTHER });
}

socket.on('connect', () => {
    console.log('🔌 متصل بالسيرفر');
    joinRoom();
});

if (socket.connected) {
    joinRoom();
}


/* ═══ الإرسال ═══ */

function sendMessage() {
    const text = inputEl.value.trim();
    if (!text) return;

    socket.emit('send_message', {
        sender: ME,
        receiver: OTHER,
        room: 'general',
        encrypted: text
    });
    inputEl.value = '';
    inputEl.focus();
}

sendBtn.addEventListener('click', sendMessage);
inputEl.addEventListener('keypress', e => {
    if (e.key === 'Enter') sendMessage();
});


/* ═══ الاستقبال ═══ */

const shownMessages = new Set();

socket.on('new_message', (data) => {
    const isBetweenUs =
        (data.sender === ME && data.receiver === OTHER) ||
        (data.sender === OTHER && data.receiver === ME);

    if (!isBetweenUs) return;

    const key = `${data.sender}|${data.time}|${data.encrypted}`;
    if (shownMessages.has(key)) return;
    shownMessages.add(key);

    addMessage(data.sender, data.encrypted, data.time);
});


/* ═══ العرض ═══ */

function addMessage(sender, text, time) {
    const div = document.createElement('div');
    div.className = 'msg ' + (sender === ME ? 'mine' : 'other');
    div.innerHTML = `
        <div class="sender">${escapeHtml(sender)}</div>
        <div class="body">${escapeHtml(text)}</div>
        <div class="time">${escapeHtml(time)}</div>
    `;
    msgsBox.appendChild(div);
    msgsBox.scrollTop = msgsBox.scrollHeight;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}


/* ═══ حالة الاتصال ═══ */

socket.on('disconnect', () => console.log('⚠️ انقطع الاتصال'));
socket.on('connect_error', (err) => console.error('خطأ في الاتصال:', err));


inputEl.focus();