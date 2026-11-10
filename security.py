"""LSPD - طبقات الحماية"""

import os
import re
from functools import wraps
from flask import request, session, abort, redirect, url_for, flash


# ═══════════════ كشف محاولات الاختراق ═══════════════

# أنماط SQL Injection
SQL_INJECTION_PATTERNS = [
    r"(\bUNION\b.*\bSELECT\b)",
    r"(\bSELECT\b.*\bFROM\b)",
    r"(\bINSERT\b.*\bINTO\b)",
    r"(\bDELETE\b.*\bFROM\b)",
    r"(\bDROP\b.*\bTABLE\b)",
    r"(\bUPDATE\b.*\bSET\b)",
    r"(--|\#|/\*|\*/)",
    r"(\bOR\b\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+)",
    r"(\bAND\b\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+)",
    r"(;.*\b(SELECT|INSERT|UPDATE|DELETE|DROP)\b)",
]

# أنماط XSS
XSS_PATTERNS = [
    r"<script[^>]*>",
    r"javascript:",
    r"onerror\s*=",
    r"onload\s*=",
    r"<iframe",
    r"<object",
    r"<embed",
    r"<img[^>]*onerror",
]

# أنماط Path Traversal
PATH_TRAVERSAL_PATTERNS = [
    r"\.\./",
    r"\.\.\\",
    r"%2e%2e",
    r"\.\.%2f",
]

# IPs محظورة مؤقتاً
BLOCKED_IPS = {}


def detect_attack(value):
    """يفحص القيمة ويرجع نوع الهجوم لو موجود"""
    if not isinstance(value, str):
        return None

    value_lower = value.lower()

    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, value, re.IGNORECASE):
            return 'sql_injection'

    for pattern in XSS_PATTERNS:
        if re.search(pattern, value_lower):
            return 'xss'

    for pattern in PATH_TRAVERSAL_PATTERNS:
        if re.search(pattern, value_lower):
            return 'path_traversal'

    return None


def get_client_ip():
    """يجيب IP العميل"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr or 'unknown'


def block_ip(ip, reason='unknown'):
    """يحظر IP مؤقتاً"""
    BLOCKED_IPS[ip] = reason
    print(f"🚫 IP محظور: {ip} - السبب: {reason}")


def is_blocked(ip):
    return ip in BLOCKED_IPS


def security_check(f):
    """Middleware - يفحص كل الطلبات"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        ip = get_client_ip()

        # فحص الحظر
        if is_blocked(ip):
            abort(403)

        # فحص GET params
        for key, value in request.args.items():
            attack = detect_attack(value)
            if attack:
                block_ip(ip, attack)
                print(f"🚨 محاولة {attack} من {ip}")
                abort(403)

        # فحص POST form
        if request.method == 'POST':
            for key, value in request.form.items():
                attack = detect_attack(value)
                if attack:
                    block_ip(ip, attack)
                    print(f"🚨 محاولة {attack} من {ip}")
                    abort(403)

        # فحص المسار
        attack = detect_attack(request.path)
        if attack:
            block_ip(ip, attack)
            abort(403)

        # فحص User-Agent
        ua = request.headers.get('User-Agent', '')
        if any(x in ua.lower() for x in ['sqlmap', 'nikto', 'nmap', 'masscan', 'hydra']):
            block_ip(ip, 'scanner')
            abort(403)

        return f(*args, **kwargs)
    return wrapper


def sanitize_input(value, max_length=5000):
    """ينظف المدخلات"""
    if not isinstance(value, str):
        return value

    value = value[:max_length]
    # شيل وسوم HTML
    value = re.sub(r'<[^>]+>', '', value)
    # شيل الرموز الخطيرة
    value = value.replace('\x00', '')

    return value.strip()


def require_rank(required_ranks):
    """يتطلب رتبة معينة"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'user' not in session:
                return redirect(url_for('login'))
            if session.get('rank') not in required_ranks and not session.get('is_admin'):
                flash('غير مصرح بالدخول', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return wrapper
    return decorator


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        if not session.get('is_admin'):
            flash('غير مصرح', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return wrapper