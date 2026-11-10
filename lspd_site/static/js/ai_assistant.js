/* ══════════════════════════════════════════════
   LSPD - AI Assistant
   ══════════════════════════════════════════════ */

(function() {
    const aiBtn = document.getElementById('aiBtn');
    const aiPanel = document.getElementById('aiPanel');
    const aiClose = document.getElementById('aiClose');
    const aiInput = document.getElementById('aiInput');
    const aiSend = document.getElementById('aiSend');
    const aiMessages = document.getElementById('aiMessages');

    if (!aiBtn) return;

    // ═══ فتح/قفل لوحة الـ AI ═══
    aiBtn.addEventListener('click', () => {
        aiPanel.classList.toggle('show');
        if (aiPanel.classList.contains('show')) {
            aiInput.focus();
        }
    });

    if (aiClose) {
        aiClose.addEventListener('click', () => {
            aiPanel.classList.remove('show');
        });
    }

    // ═══ إرسال ═══
    async function sendMessage() {
        const text = aiInput.value.trim();
        if (!text) return;

        // اعرض رسالة المستخدم
        addMessage('user', text);
        aiInput.value = '';
        aiSend.disabled = true;

        // مؤشر التحميل
        const loadingId = addMessage('ai', '...', true);

        try {
            const res = await fetch('/ai/ask', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: text })
            });

            const data = await res.json();
            removeMessage(loadingId);
            addMessage('ai', data.answer || 'معلش، مقدرتش أفهم سؤالك.');
        } catch (e) {
            removeMessage(loadingId);
            addMessage('ai', '❌ حصل خطأ، حاول تاني.');
        }

        aiSend.disabled = false;
        aiInput.focus();
    }

    aiSend.addEventListener('click', sendMessage);
    aiInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });

    // ═══ دالة إضافة رسالة ═══
    let msgCounter = 0;
    function addMessage(type, text, isLoading = false) {
        const id = 'msg-' + (msgCounter++);
        const div = document.createElement('div');
        div.className = 'ai-msg ai-msg-' + type;
        div.id = id;

        if (isLoading) {
            div.innerHTML = '<span class="ai-loading">●●●</span>';
        } else {
            div.innerHTML = formatText(text);
        }

        aiMessages.appendChild(div);
        aiMessages.scrollTop = aiMessages.scrollHeight;
        return id;
    }

    function removeMessage(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    function formatText(text) {
        // Escaping
        const div = document.createElement('div');
        div.textContent = text;
        let safe = div.innerHTML;

        // Line breaks
        safe = safe.replace(/\n/g, '<br>');

        // Bold
        safe = safe.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

        return safe;
    }

    // ═══ رسالة ترحيب ═══
    setTimeout(() => {
        if (aiMessages.children.length === 0) {
            addMessage('ai',
                '👋 **أهلاً بيك!**\n\n' +
                'أنا مساعد LSPD الذكي.\n' +
                'اسألني عن أي حاجة في النظام:\n\n' +
                '• عدد الضباط\n' +
                '• القضايا المفتوحة\n' +
                '• البلاغات النشطة\n' +
                '• معلومات عن مواطن\n' +
                '• معلومات عن مركبة\n' +
                '• مين في الشيفت'
            );
        }
    }, 300);
})();