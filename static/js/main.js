/* LSPD - الوظائف العامة */

document.addEventListener('DOMContentLoaded', () => {

    setTimeout(() => {
        document.querySelectorAll('.alert').forEach(el => {
            el.style.transition = 'opacity 0.5s';
            el.style.opacity = '0';
            setTimeout(() => el.remove(), 500);
        });
    }, 5000);

    const firstInput = document.querySelector('input[autofocus], .chat-wrap-simple input');
    if (firstInput) firstInput.focus();
});