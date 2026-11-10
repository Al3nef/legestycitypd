/* ══════════════════════════════════════════════
   LSPD - Theme + Language
   ══════════════════════════════════════════════ */

(function() {
    // ═══ الثيم ═══
    const savedTheme = localStorage.getItem('lspd-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);

    // ═══ اللغة ═══
    const savedLang = localStorage.getItem('lspd-lang') || 'ar';
    document.documentElement.setAttribute('lang', savedLang);
    document.documentElement.setAttribute('dir', savedLang === 'ar' ? 'rtl' : 'ltr');

    // ═══ تشغيل بعد تحميل الصفحة ═══
    document.addEventListener('DOMContentLoaded', () => {
        const themeBtn = document.getElementById('themeToggle');
        const langBtn = document.getElementById('langToggle');

        if (themeBtn) {
            updateThemeIcon(themeBtn);
            themeBtn.addEventListener('click', (e) => {
                e.preventDefault();
                const current = document.documentElement.getAttribute('data-theme');
                const newTheme = current === 'dark' ? 'light' : 'dark';
                document.documentElement.setAttribute('data-theme', newTheme);
                localStorage.setItem('lspd-theme', newTheme);
                updateThemeIcon(themeBtn);
            });
        }

        if (langBtn) {
            langBtn.textContent = savedLang === 'ar' ? '🌐 EN' : '🌐 AR';
            langBtn.addEventListener('click', (e) => {
                e.preventDefault();
                const current = localStorage.getItem('lspd-lang') || 'ar';
                const newLang = current === 'ar' ? 'en' : 'ar';
                localStorage.setItem('lspd-lang', newLang);
                location.reload();
            });
        }
    });

    function updateThemeIcon(btn) {
        const theme = document.documentElement.getAttribute('data-theme');
        btn.textContent = theme === 'dark' ? '☀️' : '🌙';
        btn.title = theme === 'dark' ? 'الوضع النهاري' : 'الوضع الليلي';
    }
})();