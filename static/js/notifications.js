/* ══════════════════════════════════════════════
   LSPD - نظام الإشعارات
   ══════════════════════════════════════════════ */

(function() {
    const bell = document.getElementById('notifBell');
    const count = document.getElementById('notifCount');
    const dropdown = document.getElementById('notifDropdown');
    const list = document.getElementById('notifList');

    if (!bell) return;

    /* ═══ فتح/قفل القائمة ═══ */
    bell.addEventListener('click', (e) => {
        e.stopPropagation();
        dropdown.classList.toggle('show');

        if (dropdown.classList.contains('show')) {
            loadNotifications();
        }
    });

    /* ═══ إغلاق لما تدوس بره ═══ */
    document.addEventListener('click', (e) => {
        if (!bell.contains(e.target)) {
            dropdown.classList.remove('show');
        }
    });

    /* ═══ تحميل الإشعارات ═══ */
    async function loadNotifications() {
        try {
            const res = await fetch('/api/notifications');
            const data = await res.json();

            if (data.unread > 0) {
                count.textContent = data.unread > 99 ? '99+' : data.unread;
                count.style.display = 'flex';
            } else {
                count.style.display = 'none';
            }

            if (data.notifications.length === 0) {
                list.innerHTML = '<p style="text-align:center;padding:20px;color:#7a8ca8">لا توجد إشعارات</p>';
                return;
            }

            list.innerHTML = data.notifications.map(n => `
                <a href="${n.link || '#'}"
                   class="notif-item ${n.is_read ? 'read' : 'unread'}"
                   onclick="markRead(${n.id}, event)">
                    <div class="notif-icon">${n.icon}</div>
                    <div class="notif-content">
                        <strong>${escapeHtml(n.title)}</strong>
                        ${n.message ? `<p>${escapeHtml(n.message)}</p>` : ''}
                        <small>${n.created_at}</small>
                    </div>
                </a>
            `).join('');

        } catch (e) {
            console.error('خطأ تحميل الإشعارات:', e);
            list.innerHTML = '<p style="text-align:center;padding:20px;color:#ff4757">خطأ في التحميل</p>';
        }
    }

    /* ═══ تحديث العدّاد كل 30 ثانية ═══ */
    async function updateCount() {
        try {
            const res = await fetch('/api/notifications');
            const data = await res.json();

            if (data.unread > 0) {
                count.textContent = data.unread > 99 ? '99+' : data.unread;
                count.style.display = 'flex';
            } else {
                count.style.display = 'none';
            }
        } catch (e) {}
    }

    /* ═══ تعليم إشعار كمقروء ═══ */
    window.markRead = async function(id, e) {
        try {
            await fetch(`/notifications/read/${id}`);
        } catch (err) {}
        // اكمل الرابط
    };

    /* ═══ HTML escape ═══ */
    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    /* ═══ تشغيل أول مرة ═══ */
    updateCount();
    setInterval(updateCount, 30000);
})();