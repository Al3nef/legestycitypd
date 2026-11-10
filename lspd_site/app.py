"""LSPD - الباك إند الرئيسي"""

import os
import random
import string
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, session,
    redirect, url_for, jsonify, flash, send_from_directory,
    abort
)
from flask_socketio import SocketIO, emit, join_room
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from database import db_query, init_db
from encryption import encrypt_text, decrypt_text
from ai_assistant import answer_question


# ═══════════════ 🆕 إضافة النقاط والأوسمة ═══════════════

RANK_REQUIREMENTS = {
    'Cadet': {'points': 0, 'achievements': 0},
    'Solo Cadet': {'points': 500, 'achievements': 0},
    'Officer 1': {'points': 750, 'achievements': 0},
    'Officer 2': {'points': 1000, 'achievements': 0},
    'Officer 3': {'points': 1200, 'achievements': 1},
    'Senior Officer': {'points': 1400, 'achievements': 2},
    'Senior Lead Officer': {'points': 2000, 'achievements': 3},
    'Sergeant': {'points': 2400, 'achievements': 5},
    'First Sergeant': {'points': 3000, 'achievements': 6},
    'Staff Sergeant': {'points': 4500, 'achievements': 7},
    'Lieutenant': {'points': 7000, 'achievements': 10},
    'First Lieutenant': {'points': 9000, 'achievements': 12},
    'Captain': {'points': 12000, 'achievements': 15},
    'Major': {'points': 15000, 'achievements': 20},
    'Colonel': {'points': 20000, 'achievements': 25},
    'Brigadier General': {'points': 25000, 'achievements': 30},
    'Major General': {'points': 30000, 'achievements': 35},
    'Lieutenant General': {'points': 40000, 'achievements': 40},
    'General': {'points': 50000, 'achievements': 50},
}

def can_manage_points():
    return session.get('rank') in ['General', 'Lieutenant General', 'Major General', 'Brigadier General', 'Colonel']

def can_manage_achievements():
    return session.get('rank') in ['General', 'Lieutenant General', 'Major General', 'Brigadier General', 'Colonel']


app = Flask(__name__)

app.config['SECRET_KEY'] = 'LSPD-FIXED-FLASK-SECRET-2024-X9K7M'
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25
)


# ═══════════════ الرتب ═══════════════

CHAT_ALLOWED_RANKS = ['Colonel', 'Brigadier General', 'Major General', 'Lieutenant General', 'General']
DELETE_ALLOWED_RANKS = ['Colonel', 'Brigadier General', 'Major General', 'Lieutenant General', 'General']
CASE_CREATE_ALLOWED_RANKS = ['Colonel', 'Brigadier General', 'Major General', 'Lieutenant General', 'General']

ALL_RANKS = [
    'Cadet', 'Solo Cadet',
    'Officer 1', 'Officer 2', 'Officer 3',
    'Senior Officer', 'Senior Lead Officer',
    'Sergeant', 'First Sergeant', 'Staff Sergeant',
    'Lieutenant', 'First Lieutenant',
    'Captain', 'Major',
    'Lieutenant Colonel', 'Colonel',
    'Brigadier General', 'Major General',
    'Lieutenant General', 'General'
]


def can_chat(rank):
    return rank in CHAT_ALLOWED_RANKS


def can_delete():
    return (session.get('is_admin') and session.get('rank') in DELETE_ALLOWED_RANKS)


def can_create_case():
    return session.get('rank') in CASE_CREATE_ALLOWED_RANKS


@app.context_processor
def inject_globals():
    return {
        'can_chat': can_chat,
        'can_delete': can_delete,
        'can_create_case': can_create_case,
        'can_manage_points': can_manage_points,
        'can_manage_achievements': can_manage_achievements,
        'CHAT_ALLOWED_RANKS': CHAT_ALLOWED_RANKS,
        'RANK_REQUIREMENTS': RANK_REQUIREMENTS
    }


@app.after_request
def add_security_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'same-origin'
    return response


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


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


def sanitize(value, max_len=5000):
    if not isinstance(value, str):
        return value
    value = value[:max_len]
    return value.strip()


def log_activity(user, action, details=''):
    try:
        ip = request.remote_addr or 'unknown'
        db_query(
            """INSERT INTO activity_log (user, action, details, ip)
               VALUES (?, ?, ?, ?)""",
            (user, action, details, ip),
            commit=True
        )
    except:
        pass


def create_notification(user, title, message='', icon='🔔', link=None):
    try:
        db_query(
            """INSERT INTO notifications (user, title, message, icon, link)
               VALUES (?, ?, ?, ?, ?)""",
            (user, title, message, icon, link),
            commit=True
        )
    except:
        pass


# ═══════════════ المصادقة ═══════════════

LOGIN_ATTEMPTS = {}
MAX_ATTEMPTS = 5
LOCKOUT = 300


@app.route('/')
def index():
    return redirect(url_for('dashboard') if 'user' in session else url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        ip = request.remote_addr or 'unknown'
        now = datetime.now()

        if ip in LOGIN_ATTEMPTS:
            attempts, lock_time = LOGIN_ATTEMPTS[ip]
            if attempts >= MAX_ATTEMPTS:
                if (now - lock_time).seconds < LOCKOUT:
                    remaining = LOCKOUT - (now - lock_time).seconds
                    flash(f'محظور مؤقتاً. حاول بعد {remaining} ثانية', 'danger')
                    return render_template('login.html')
                else:
                    LOGIN_ATTEMPTS[ip] = (0, now)

        username = sanitize(request.form.get('username', ''), 50)
        password = request.form.get('password', '')[:200]

        if not username or not password:
            flash('جميع الحقول مطلوبة', 'danger')
            return render_template('login.html')

        row = db_query("SELECT * FROM users WHERE username=?", (username,), one=True)

        if row and check_password_hash(row['password_hash'], password):
            LOGIN_ATTEMPTS[ip] = (0, now)
            session.clear()
            session['user'] = row['username']
            session['rank'] = row['rank']
            session['is_admin'] = bool(row['is_admin'])
            session.permanent = True
            flash('تم تسجيل الدخول', 'success')

            log_activity(row['username'], 'تسجيل دخول', f'IP: {ip}')

            return redirect(url_for('dashboard'))

        attempts = LOGIN_ATTEMPTS.get(ip, (0, now))[0] + 1
        LOGIN_ATTEMPTS[ip] = (attempts, now)

        if attempts >= MAX_ATTEMPTS:
            flash('تجاوزت عدد المحاولات. انتظر 5 دقايق', 'danger')
        else:
            flash(f'بيانات غلط ({MAX_ATTEMPTS - attempts} محاولات متبقية)', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    if 'user' in session:
        log_activity(session['user'], 'تسجيل خروج', '')
    session.clear()
    flash('تم تسجيل الخروج', 'success')
    return redirect(url_for('login'))


# ═══════════════ لوحة التحكم ═══════════════

@app.route('/dashboard')
@login_required
def dashboard():
    infos_raw = db_query("SELECT * FROM infos ORDER BY id DESC LIMIT 5")
    infos = [{
        'title': i['title'],
        'author': i['author'],
        'created_at': i['created_at'],
        'classification': i['classification'],
    } for i in infos_raw]

    stats = {
        'users': db_query("SELECT COUNT(*) as c FROM users", one=True)['c'],
        'messages': db_query("SELECT COUNT(*) as c FROM messages", one=True)['c'],
        'infos': db_query("SELECT COUNT(*) as c FROM infos", one=True)['c'],
        'cases': db_query("SELECT COUNT(*) as c FROM cases", one=True)['c'],
        'open_cases': db_query("SELECT COUNT(*) as c FROM cases WHERE status='OPEN'", one=True)['c'],
    }

    return render_template('dashboard.html', infos=infos, stats=stats)


# ═══════════════ 👕 Dress Code (اللبس الرسمي) ═══════════════

@app.route('/dress_code')
@login_required
def dress_code():
    dress_data = [
        {'rank_name': 'Cadet', 'rank_ar': 'كاديت', 'image': 'cadet.png', 'shirts': 161, 'pants': 5, 'hats': 3, 'masks': 0, 'accessories': 0, 'armor': 0, 'belts': 0},
        {'rank_name': 'Solo Cadet', 'rank_ar': 'سولو كاديت', 'image': 'solo_cadet.png', 'shirts': 98, 'pants': 12, 'hats': 12, 'masks': 0, 'accessories': 0, 'armor': 0, 'belts': 0},
        {'rank_name': 'Officer 1', 'rank_ar': 'أوفيسر 1', 'image': 'officer1.png', 'shirts': 23, 'pants': 5, 'hats': 3, 'masks': 0, 'accessories': 0, 'armor': 0, 'belts': 0},
        {'rank_name': 'Officer 2', 'rank_ar': 'أوفيسر 2', 'image': 'officer2.png', 'shirts': 279, 'pants': 12, 'hats': 15, 'masks': 2, 'accessories': 2, 'armor': 17, 'belts': 3},
        {'rank_name': 'Officer 3', 'rank_ar': 'أوفيسر 3', 'image': 'officer3.png', 'shirts': 279, 'pants': 12, 'hats': 15, 'masks': 2, 'accessories': 2, 'armor': 17, 'belts': 3},
        {'rank_name': 'Senior Officer', 'rank_ar': 'سينيور أوفيسر', 'image': 'senior_officer.png', 'shirts': 285, 'pants': 12, 'hats': 15, 'masks': 0, 'accessories': 0, 'armor': 17, 'belts': 3},
        {'rank_name': 'Sergeant', 'rank_ar': 'سارجنت', 'image': 'sergeant.png', 'shirts': 290, 'pants': 12, 'hats': 15, 'masks': 0, 'accessories': 0, 'armor': 17, 'belts': 3},
        {'rank_name': 'Staff Sergeant', 'rank_ar': 'ستاف سارجنت', 'image': 'staff_sergeant.png', 'shirts': 282, 'pants': 12, 'hats': 17, 'masks': 0, 'accessories': 0, 'armor': 17, 'belts': 3},
        {'rank_name': 'Lieutenant', 'rank_ar': 'ليوتينانت', 'image': 'lieutenant.png', 'shirts': 268, 'pants': 12, 'hats': 46, 'masks': 0, 'accessories': 0, 'armor': 17, 'belts': 3},
        {'rank_name': 'First Lieutenant', 'rank_ar': 'فيرست ليوتينانت', 'image': 'first_lieutenant.png', 'shirts': 186, 'pants': 12, 'hats': 17, 'masks': 0, 'accessories': 0, 'armor': 17, 'belts': 3},
        {'rank_name': 'Captain', 'rank_ar': 'كابتن', 'image': 'captain.png', 'shirts': 173, 'pants': 12, 'hats': 20, 'masks': 0, 'accessories': 0, 'armor': 17, 'belts': 3},
        {'rank_name': 'Major', 'rank_ar': 'ميجور', 'image': 'major.png', 'shirts': 0, 'pants': 0, 'hats': 0, 'masks': 0, 'accessories': 0, 'armor': 0, 'belts': 0}
    ]
    return render_template('dress_code.html', dress_data=dress_data)

# ═══════════════ 📻 Radio Protocols (البروتوكولات) ═══════════════

@app.route('/radio_protocols')
@login_required
def radio_protocols():
    return render_template('radio_protocols.html')


# ═══════════════ المحادثات ═══════════════

@app.route('/chat')
@login_required
def chat_list():
    if not can_chat(session.get('rank')):
        flash('المحادثات متاحة فقط للرتب من Colonel فما فوق', 'danger')
        return redirect(url_for('dashboard'))

    users = db_query(
        """SELECT username, badge, rank FROM users
           WHERE username != ?
           AND rank IN ('Colonel', 'Brigadier General', 'Major General',
                        'Lieutenant General', 'General')
           ORDER BY rank""",
        (session['user'],)
    )
    unread = {}
    for u in users:
        row = db_query(
            """SELECT COUNT(*) as c FROM messages
               WHERE sender=? AND receiver=? AND is_read=0""",
            (u['username'], session['user']),
            one=True
        )
        unread[u['username']] = row['c']

    return render_template('chat_list.html', users=users, unread=unread)


@app.route('/chat/<other>')
@login_required
def chat_room(other):
    if not can_chat(session.get('rank')):
        flash('المحادثات متاحة فقط للرتب من Colonel فما فوق', 'danger')
        return redirect(url_for('dashboard'))

    other = sanitize(other, 50)
    other_user = db_query("SELECT rank FROM users WHERE username=?", (other,), one=True)

    if not other_user:
        flash('المستخدم غير موجود', 'danger')
        return redirect(url_for('chat_list'))

    if not can_chat(other_user['rank']):
        flash('لا يمكنك محادثة هذا الضابط', 'danger')
        return redirect(url_for('chat_list'))

    if other == session['user']:
        flash('لا يمكنك محادثة نفسك', 'danger')
        return redirect(url_for('chat_list'))

    db_query(
        "UPDATE messages SET is_read=1 WHERE sender=? AND receiver=?",
        (other, session['user']),
        commit=True
    )

    return render_template('chat_room.html', other=other)


@app.route('/api/history/<other>')
@login_required
def api_history(other):
    if not can_chat(session.get('rank')):
        return jsonify([])

    me = session['user']
    other = sanitize(other, 50)

    rows = db_query(
        """SELECT * FROM messages
           WHERE (sender=? AND receiver=?) OR (sender=? AND receiver=?)
           ORDER BY id ASC LIMIT 200""",
        (me, other, other, me)
    )
    return jsonify([{
        'sender': r['sender'],
        'receiver': r['receiver'],
        'encrypted': r['encrypted'],
        'time': r['created_at']
    } for r in rows])


# ═══════════════ المعلومات ═══════════════

@app.route('/info')
@login_required
def info_list():
    rows = db_query("SELECT * FROM infos ORDER BY id DESC")
    infos = []
    for r in rows:
        d = dict(r)
        d['image'] = d.get('image')
        infos.append(d)
    return render_template('info.html', infos=infos)


@app.route('/info/add', methods=['POST'])
@login_required
def info_add():
    title = sanitize(request.form.get('title', ''), 200)
    body = sanitize(request.form.get('body', ''), 5000)

    if not title or not body:
        flash('العنوان والمحتوى مطلوبان', 'danger')
        return redirect(url_for('info_list'))

    image_filename = None
    file = request.files.get('image')

    if file and file.filename:
        if not allowed_file(file.filename):
            flash('نوع الصورة غير مسموح', 'danger')
            return redirect(url_for('info_list'))

        file.seek(0, 2)
        size = file.tell()
        file.seek(0)
        if size > 5 * 1024 * 1024:
            flash('حجم الصورة كبير (الحد 5 ميجا)', 'danger')
            return redirect(url_for('info_list'))

        ext = file.filename.rsplit('.', 1)[1].lower()
        unique_name = f"{int(datetime.now().timestamp())}_{random.randint(1000,9999)}.{ext}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
        image_filename = unique_name

    db_query(
        """INSERT INTO infos (title, encrypted_body, category, classification, author, image)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            title, body,
            sanitize(request.form.get('category', 'general'), 50),
            sanitize(request.form.get('classification', 'CONFIDENTIAL'), 20),
            session['user'],
            image_filename
        ),
        commit=True
    )

    log_activity(session['user'], 'إضافة معلومة', title)
    flash('تم إضافة المعلومة', 'success')
    return redirect(url_for('info_list'))


@app.route('/info/delete/<int:info_id>')
@login_required
@admin_required
def info_delete(info_id):
    row = db_query("SELECT image FROM infos WHERE id=?", (info_id,), one=True)
    if row and row['image']:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], row['image']))
        except:
            pass

    db_query("DELETE FROM infos WHERE id=?", (info_id,), commit=True)
    log_activity(session['user'], 'حذف معلومة', f'#{info_id}')
    flash('تم الحذف', 'success')
    return redirect(url_for('info_list'))


@app.route('/info/<int:info_id>/remove_image', methods=['POST'])
@login_required
@admin_required
def info_remove_image(info_id):
    row = db_query("SELECT image FROM infos WHERE id=?", (info_id,), one=True)
    if row and row['image']:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], row['image']))
        except:
            pass
        db_query("UPDATE infos SET image=NULL WHERE id=?", (info_id,), commit=True)
        flash('تم حذف الصورة', 'success')
    else:
        flash('مفيش صورة', 'danger')

    return redirect(url_for('info_list'))


@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    filename = secure_filename(filename)
    if not filename or '..' in filename:
        abort(404)

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(filepath):
        abort(404)

    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ═══════════════ أدوات التشفير ═══════════════

@app.route('/tools', methods=['GET', 'POST'])
@login_required
def tools():
    result = None
    text = ''
    if request.method == 'POST':
        text = request.form.get('text', '')[:5000]
        action = request.form.get('action', 'encrypt')
        try:
            if action == 'encrypt':
                result = encrypt_text(text)
            else:
                result = decrypt_text(text)
        except Exception as e:
            result = f"[خطأ: {e}]"
    return render_template('tools.html', result=result, text=text)


# ═══════════════ لوحة الإدارة ═══════════════

@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    users = db_query("""
        SELECT * FROM users 
        ORDER BY 
            CASE rank
                WHEN 'General' THEN 19
                WHEN 'Lieutenant General' THEN 18
                WHEN 'Major General' THEN 17
                WHEN 'Brigadier General' THEN 16
                WHEN 'Colonel' THEN 15
                WHEN 'Lieutenant Colonel' THEN 14
                WHEN 'Major' THEN 13
                WHEN 'Captain' THEN 12
                WHEN 'First Lieutenant' THEN 11
                WHEN 'Lieutenant' THEN 10
                WHEN 'Staff Sergeant' THEN 9
                WHEN 'First Sergeant' THEN 8
                WHEN 'Sergeant' THEN 7
                WHEN 'Senior Lead Officer' THEN 6
                WHEN 'Senior Officer' THEN 5
                WHEN 'Officer 3' THEN 4
                WHEN 'Officer 2' THEN 3
                WHEN 'Officer 1' THEN 2
                WHEN 'Solo Cadet' THEN 1
                WHEN 'Cadet' THEN 0
                ELSE -1
            END DESC, id ASC
    """)
    return render_template('admin.html', users=users)


@app.route('/admin/add_user', methods=['POST'])
@login_required
@admin_required
def admin_add_user():
    username = sanitize(request.form.get('username', ''), 50)
    password = request.form.get('password', '')[:200]
    badge = sanitize(request.form.get('badge', ''), 20)
    rank = request.form.get('rank', 'Officer 1')
    is_admin = 1 if request.form.get('is_admin') else 0

    if not username or not password or not badge:
        flash('جميع الحقول مطلوبة', 'danger')
        return redirect(url_for('admin_panel'))

    if rank not in ALL_RANKS:
        flash('رتبة غير صحيحة', 'danger')
        return redirect(url_for('admin_panel'))

    if len(password) < 4:
        flash('كلمة المرور قصيرة', 'danger')
        return redirect(url_for('admin_panel'))

    if db_query("SELECT id FROM users WHERE username=?", (username,), one=True):
        flash('الاسم موجود', 'danger')
        return redirect(url_for('admin_panel'))

    if db_query("SELECT id FROM users WHERE badge=?", (badge,), one=True):
        flash('رقم الشرطة مستخدم', 'danger')
        return redirect(url_for('admin_panel'))

    db_query(
        """INSERT INTO users (username, password_hash, badge, rank, is_admin, points)
           VALUES (?, ?, ?, ?, ?, 0)""",
        (username, generate_password_hash(password), badge, rank, is_admin),
        commit=True
    )

    log_activity(session['user'], 'إضافة مستخدم', f'{username} - {rank}')

    create_notification(
        username,
        'مرحباً بك في LSPD 🎉',
        f'تم إنشاء حسابك برتبة {rank} بواسطة {session["user"]}',
        '🎉',
        url_for('profile')
    )

    flash(f'تم إضافة {username}', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/admin/edit_user/<old_username>', methods=['POST'])
@login_required
@admin_required
def admin_edit_user(old_username):
    new_username = sanitize(request.form.get('new_username', ''), 50)
    new_badge = sanitize(request.form.get('new_badge', ''), 20)
    new_password = request.form.get('new_password', '')[:200]

    if not new_username or not new_badge:
        flash('الاسم ورقم الشرطة مطلوبان', 'danger')
        return redirect(url_for('admin_panel'))

    existing = db_query(
        "SELECT id FROM users WHERE username=? AND username!=?",
        (new_username, old_username), one=True
    )
    if existing:
        flash('الاسم موجود', 'danger')
        return redirect(url_for('admin_panel'))

    existing = db_query(
        "SELECT id FROM users WHERE badge=? AND username!=?",
        (new_badge, old_username), one=True
    )
    if existing:
        flash('رقم الشرطة مستخدم', 'danger')
        return redirect(url_for('admin_panel'))

    db_query(
        "UPDATE users SET username=?, badge=? WHERE username=?",
        (new_username, new_badge, old_username),
        commit=True
    )

    if new_password and session.get('rank') == 'General':
        if len(new_password) < 4:
            flash('كلمة المرور قصيرة', 'danger')
            return redirect(url_for('admin_panel'))
        db_query(
            "UPDATE users SET password_hash=? WHERE username=?",
            (generate_password_hash(new_password), new_username),
            commit=True
        )
        flash(f'تم تعديل {old_username} وكلمة المرور', 'success')
    else:
        flash(f'تم تعديل {old_username} → {new_username}', 'success')

    db_query("UPDATE messages SET sender=? WHERE sender=?",
             (new_username, old_username), commit=True)
    db_query("UPDATE messages SET receiver=? WHERE receiver=?",
             (new_username, old_username), commit=True)
    db_query("UPDATE duty_roster SET officer=? WHERE officer=?",
             (new_username, old_username), commit=True)

    if session.get('user') == old_username:
        session['user'] = new_username

    log_activity(session['user'], 'تعديل مستخدم', f'{old_username} → {new_username}')

    create_notification(
        new_username,
        'تم تحديث بياناتك ✏️',
        f'تم تعديل بياناتك بواسطة {session["user"]}',
        '✏️',
        url_for('profile')
    )

    return redirect(url_for('admin_panel'))


@app.route('/admin/rank/<username>/<new_rank>')
@login_required
@admin_required
def admin_change_rank(username, new_rank):
    if new_rank not in ALL_RANKS:
        flash('رتبة غير صحيحة', 'danger')
        return redirect(url_for('admin_panel'))

    user_data = db_query("SELECT rank, points FROM users WHERE username=?", (username,), one=True)
    if not user_data:
        flash('المستخدم غير موجود', 'danger')
        return redirect(url_for('admin_panel'))

    old_rank = user_data['rank']
    user_points = user_data['points']

    if old_rank == new_rank:
        flash(f'{username} عنده نفس الرتبة بالفعل', 'danger')
        return redirect(url_for('admin_panel'))

    req = RANK_REQUIREMENTS.get(new_rank, {'points': 0, 'achievements': 0})
    if user_points < req['points']:
        flash(f'⚠️ تحذير: {username} لا يمتلك النقاط المطلوبة لرتبة {new_rank} (مطلوب {req["points"]} نقطة)!', 'danger')

    ach_count = db_query("SELECT COUNT(*) as c FROM user_achievements WHERE user=?", (username,), one=True)['c']
    if ach_count < req['achievements']:
        flash(f'⚠️ تحذير: {username} لا يمتلك الأوسمة المطلوبة لرتبة {new_rank} (مطلوب {req["achievements"]} وسام)!', 'danger')

    try:
        old_index = ALL_RANKS.index(old_rank)
        new_index = ALL_RANKS.index(new_rank)
        if new_index > old_index:
            is_promotion = True
            action_text = 'ترقية'
            notif_title = 'تم ترقيتك 🎖️'
            notif_icon = '🎖️'
        else:
            is_promotion = False
            action_text = 'تنتيل'
            notif_title = 'تم تنتيلك ⬇️'
            notif_icon = '⬇️'
    except ValueError:
        is_promotion = True
        action_text = 'تعديل رتبة'
        notif_title = 'تم تحديث رتبتك 🎖️'
        notif_icon = '🎖️'

    db_query("UPDATE users SET rank=? WHERE username=?", (new_rank, username), commit=True)
    db_query("UPDATE duty_roster SET rank=? WHERE officer=?", (new_rank, username), commit=True)

    if is_promotion:
        message = f'تم ترقيتك من "{old_rank}" إلى "{new_rank}" بواسطة {session["user"]}'
    else:
        message = f'تم تنتيلك من "{old_rank}" إلى "{new_rank}" بواسطة {session["user"]}'

    create_notification(username, notif_title, message, notif_icon, url_for('profile'))
    log_activity(session['user'], action_text, f'{username}: {old_rank} → {new_rank}')

    if is_promotion:
        flash(f'تم ترقية {username} إلى {new_rank}', 'success')
    else:
        flash(f'تم تنتيل {username} إلى {new_rank}', 'success')

    return redirect(url_for('admin_panel'))


# 🆕 API جديد للسحب والإفلات
@app.route('/api/reorder_users', methods=['POST'])
@login_required
@admin_required
def api_reorder_users():
    data = request.get_json()
    if not data or 'order' not in data:
        return jsonify({'success': False})
    
    for i, uid in enumerate(data['order']):
        db_query("UPDATE users SET id = ? WHERE id = ?", (i+1, uid), commit=True)
        
    return jsonify({'success': True})


@app.route('/admin/make_admin/<username>')
@login_required
@admin_required
def admin_make_admin(username):
    db_query("UPDATE users SET is_admin=1 WHERE username=?", (username,), commit=True)
    log_activity(session['user'], 'منح أدمن', username)

    create_notification(
        username,
        'تم منحك صلاحيات أدمن 🔑',
        f'تم منحك صلاحيات كاملة بواسطة {session["user"]}',
        '🔑',
        url_for('dashboard')
    )

    flash(f'تم منح {username} صلاحيات أدمن', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/admin/remove_admin/<username>')
@login_required
@admin_required
def admin_remove_admin(username):
    if username == session['user']:
        flash('لا يمكنك إزالة صلاحياتك', 'danger')
        return redirect(url_for('admin_panel'))
    db_query("UPDATE users SET is_admin=0 WHERE username=?", (username,), commit=True)
    log_activity(session['user'], 'إزالة أدمن', username)

    create_notification(
        username,
        'تم إزالة صلاحيات الأدمن ⚠️',
        f'تم إزالة صلاحياتك بواسطة {session["user"]}',
        '⚠️',
        url_for('dashboard')
    )

    flash(f'تم إزالة صلاحيات {username}', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/admin/delete/<username>')
@login_required
@admin_required
def admin_delete(username):
    if username == session['user']:
        return redirect(url_for('admin_panel'))
    db_query("DELETE FROM users WHERE username=?", (username,), commit=True)
    db_query("DELETE FROM messages WHERE sender=? OR receiver=?",
             (username, username), commit=True)
    db_query("DELETE FROM duty_roster WHERE officer=?", (username,), commit=True)
    log_activity(session['user'], 'حذف مستخدم', username)
    flash(f'تم حذف {username}', 'success')
    return redirect(url_for('admin_panel'))


# ═══════════════ 🆕 إدارة النقاط والأوسمة ═══════════════

@app.route('/points_management')
@login_required
def points_management():
    # التعديل هنا: رتبنا حسب الرتبة الأول (الجنرال فوق) وبعدين النقاط
    users = db_query("""
        SELECT * FROM users 
        ORDER BY 
            CASE rank
                WHEN 'General' THEN 19
                WHEN 'Lieutenant General' THEN 18
                WHEN 'Major General' THEN 17
                WHEN 'Brigadier General' THEN 16
                WHEN 'Colonel' THEN 15
                WHEN 'Lieutenant Colonel' THEN 14
                WHEN 'Major' THEN 13
                WHEN 'Captain' THEN 12
                WHEN 'First Lieutenant' THEN 11
                WHEN 'Lieutenant' THEN 10
                WHEN 'Staff Sergeant' THEN 9
                WHEN 'First Sergeant' THEN 8
                WHEN 'Sergeant' THEN 7
                WHEN 'Senior Lead Officer' THEN 6
                WHEN 'Senior Officer' THEN 5
                WHEN 'Officer 3' THEN 4
                WHEN 'Officer 2' THEN 3
                WHEN 'Officer 1' THEN 2
                WHEN 'Solo Cadet' THEN 1
                WHEN 'Cadet' THEN 0
                ELSE -1
            END DESC, points DESC
    """)
    achievements = db_query("SELECT * FROM achievements ORDER BY id")

    stats = {
        'total_points': db_query("SELECT SUM(points) as s FROM users", one=True)['s'] or 0,
        'total_achievements': db_query("SELECT COUNT(*) as c FROM user_achievements", one=True)['c'],
        'top_user': db_query("SELECT username, points FROM users ORDER BY points DESC LIMIT 1", one=True)
    }

    return render_template('points_management.html', users=users, achievements=achievements, stats=stats)


@app.route('/points_management/give', methods=['POST'])
@login_required
def give_points():
    if not can_manage_points():
        flash('غير مصرح', 'danger')
        return redirect(url_for('dashboard'))

    username = sanitize(request.form.get('username', ''), 50)
    amount = request.form.get('amount', 0, type=int)
    reason = sanitize(request.form.get('reason', ''), 200)

    if not username or amount == 0:
        flash('الرجاء إدخال اسم المستخدم وعدد النقاط', 'danger')
        return redirect(url_for('points_management'))

    db_query("UPDATE users SET points = points + ? WHERE username=?", (amount, username), commit=True)
    db_query("INSERT INTO points_log (user, amount, reason, given_by) VALUES (?, ?, ?, ?)", (username, amount, reason, session['user']), commit=True)

    emoji = '➕' if amount > 0 else '➖'
    create_notification(username, f'{emoji} {"زيادة" if amount > 0 else "خصم"} نقاط', f'تم {"إضافة" if amount > 0 else "خصم"} {abs(amount)} نقطة. السبب: {reason}', emoji, url_for('profile'))
    log_activity(session['user'], 'تعديل نقاط', f'{username}: {amount}')
    flash(f'تم تعديل نقاط {username} بنجاح', 'success')
    return redirect(url_for('points_management'))


@app.route('/points_management/award_achievement', methods=['POST'])
@login_required
def award_achievement_route():
    if not can_manage_achievements():
        flash('غير مصرح', 'danger')
        return redirect(url_for('dashboard'))

    username = sanitize(request.form.get('username', ''), 50)
    achievement_id = request.form.get('achievement_id', 0, type=int)

    if not username or not achievement_id:
        flash('الرجاء اختيار المستخدم والوسام', 'danger')
        return redirect(url_for('points_management'))

    achievement = db_query("SELECT * FROM achievements WHERE id=?", (achievement_id,), one=True)
    if not achievement:
        flash('الوسام غير موجود', 'danger')
        return redirect(url_for('points_management'))

    existing = db_query("SELECT id FROM user_achievements WHERE user=? AND achievement_id=?", (username, achievement_id), one=True)
    if existing:
        flash(f'{username} حصل على هذا الوسام بالفعل', 'danger')
        return redirect(url_for('points_management'))

    db_query("INSERT INTO user_achievements (user, achievement_id, awarded_by) VALUES (?, ?, ?)", (username, achievement_id, session['user']), commit=True)

    if achievement['points_reward'] > 0:
        db_query("UPDATE users SET points = points + ? WHERE username=?", (achievement['points_reward'], username), commit=True)
        db_query("INSERT INTO points_log (user, amount, reason, given_by) VALUES (?, ?, ?, ?)", (username, achievement['points_reward'], f'مكافأة وسام: {achievement["name"]}', session['user']), commit=True)

    create_notification(username, f'{achievement["icon"]} حصلت على وسام', f'تم منحك وسام "{achievement["name"]}" بواسطة {session["user"]} (+{achievement["points_reward"]} نقطة)', achievement['icon'], url_for('profile'))
    log_activity(session['user'], 'منح وسام', f'{username}: {achievement["name"]}')
    flash(f'تم منح الوسام لـ {username}', 'success')
    return redirect(url_for('points_management'))


# ═══════════════ القضايا ═══════════════

def generate_case_number():
    year = datetime.now().year
    num = ''.join(random.choices(string.digits, k=4))
    return f"LSPD-{year}-{num}"


@app.route('/cases')
@login_required
def cases_list():
    status_filter = request.args.get('status', 'ALL')
    priority_filter = request.args.get('priority', 'ALL')

    query = "SELECT * FROM cases WHERE 1=1"
    params = []

    if status_filter in ('OPEN', 'INVESTIGATING', 'CLOSED', 'ARCHIVED'):
        query += " AND status=?"
        params.append(status_filter)
    if priority_filter in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'):
        query += " AND priority=?"
        params.append(priority_filter)

    query += " ORDER BY id DESC"

    rows = db_query(query, params)
    cases = [{
        'id': r['id'],
        'case_number': r['case_number'],
        'title': r['title'],
        'description': r['encrypted_description'],
        'suspect': r['suspect'],
        'status': r['status'],
        'priority': r['priority'],
        'lead_officer': r['lead_officer'],
        'location': r['location'],
        'created_at': r['created_at'],
    } for r in rows]

    stats = {
        'total': db_query("SELECT COUNT(*) as c FROM cases", one=True)['c'],
        'open': db_query("SELECT COUNT(*) as c FROM cases WHERE status='OPEN'", one=True)['c'],
        'closed': db_query("SELECT COUNT(*) as c FROM cases WHERE status='CLOSED'", one=True)['c'],
        'critical': db_query("SELECT COUNT(*) as c FROM cases WHERE priority='CRITICAL'", one=True)['c'],
    }

    return render_template('cases.html',
                          cases=cases, stats=stats,
                          status_filter=status_filter,
                          priority_filter=priority_filter)


@app.route('/cases/add', methods=['POST'])
@login_required
def case_add():
    if not can_create_case():
        flash('فتح القضايا متاح للرتب من Colonel فما فوق فقط', 'danger')
        return redirect(url_for('cases_list'))

    title = sanitize(request.form.get('title', ''), 200)
    description = sanitize(request.form.get('description', ''), 5000)

    if not title or not description:
        flash('العنوان والوصف مطلوبان', 'danger')
        return redirect(url_for('cases_list'))

    case_num = generate_case_number()

    db_query(
        """INSERT INTO cases
           (case_number, title, encrypted_description, suspect, status,
            priority, lead_officer, location)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (case_num, title, description,
         sanitize(request.form.get('suspect', ''), 100),
         request.form.get('status', 'OPEN'),
         request.form.get('priority', 'MEDIUM'),
         session['user'],
         sanitize(request.form.get('location', ''), 200)),
        commit=True
    )

    log_activity(session['user'], 'فتح قضية', f'{case_num}: {title}')

    higher_ups = db_query(
        """SELECT username FROM users
           WHERE rank IN ('Colonel', 'Brigadier General', 'Major General',
                          'Lieutenant General', 'General')"""
    )
    for u in higher_ups:
        if u['username'] != session['user']:
            create_notification(
                u['username'],
                'قضية جديدة 📂',
                f'{session["user"]} فتح: {title}',
                '📂',
                url_for('cases_list')
            )

    flash(f'تم فتح القضية: {case_num}', 'success')
    return redirect(url_for('cases_list'))


@app.route('/cases/<int:case_id>')
@login_required
def case_detail(case_id):
    case = db_query("SELECT * FROM cases WHERE id=?", (case_id,), one=True)
    if not case:
        flash('القضية غير موجودة', 'danger')
        return redirect(url_for('cases_list'))

    evidence_rows = db_query(
        "SELECT * FROM evidence WHERE case_id=? ORDER BY id DESC",
        (case_id,)
    )

    evidence = []
    for e in evidence_rows:
        d = dict(e)
        d['image'] = d.get('image')
        evidence.append(d)

    case_data = {
        'id': case['id'],
        'case_number': case['case_number'],
        'title': case['title'],
        'description': case['encrypted_description'],
        'suspect': case['suspect'],
        'status': case['status'],
        'priority': case['priority'],
        'lead_officer': case['lead_officer'],
        'location': case['location'],
        'created_at': case['created_at'],
        'updated_at': case['updated_at'],
    }

    return render_template('case_detail.html', case=case_data, evidence=evidence)


@app.route('/cases/<int:case_id>/evidence', methods=['POST'])
@login_required
def case_add_evidence(case_id):
    content = sanitize(request.form.get('content', ''), 5000)
    if not content:
        flash('محتوى الدليل مطلوب', 'danger')
        return redirect(url_for('case_detail', case_id=case_id))

    image_filename = None
    file = request.files.get('image')
    if file and file.filename:
        if allowed_file(file.filename):
            file.seek(0, 2)
            size = file.tell()
            file.seek(0)
            if size > 5 * 1024 * 1024:
                flash('حجم الصورة كبير (الحد 5 ميجا)', 'danger')
                return redirect(url_for('case_detail', case_id=case_id))

            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_name = f"ev_{int(datetime.now().timestamp())}_{random.randint(1000,9999)}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
            image_filename = unique_name

    db_query(
        """INSERT INTO evidence (case_id, encrypted_content, evidence_type, image, added_by)
           VALUES (?, ?, ?, ?, ?)""",
        (case_id, content,
         request.form.get('evidence_type', 'physical'),
         image_filename,
         session['user']),
        commit=True
    )

    log_activity(session['user'], 'إضافة دليل', f'قضية #{case_id}')
    flash('تم إضافة الدليل', 'success')
    return redirect(url_for('case_detail', case_id=case_id))


@app.route('/cases/<int:case_id>/status/<new_status>')
@login_required
def case_update_status(case_id, new_status):
    if new_status not in ('OPEN', 'INVESTIGATING', 'CLOSED', 'ARCHIVED'):
        flash('حالة غير صحيحة', 'danger')
        return redirect(url_for('case_detail', case_id=case_id))

    db_query(
        "UPDATE cases SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (new_status, case_id),
        commit=True
    )
    log_activity(session['user'], 'تحديث قضية', f'#{case_id} → {new_status}')
    flash('تم تحديث الحالة', 'success')
    return redirect(url_for('case_detail', case_id=case_id))


@app.route('/cases/<int:case_id>/delete')
@login_required
@admin_required
def case_delete(case_id):
    evidence_images = db_query(
        "SELECT image FROM evidence WHERE case_id=? AND image IS NOT NULL",
        (case_id,)
    )
    for e in evidence_images:
        if e['image']:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], e['image']))
            except:
                pass

    db_query("DELETE FROM evidence WHERE case_id=?", (case_id,), commit=True)
    db_query("DELETE FROM cases WHERE id=?", (case_id,), commit=True)
    log_activity(session['user'], 'حذف قضية', f'#{case_id}')
    flash('تم حذف القضية', 'success')
    return redirect(url_for('cases_list'))


# ═══════════════ القيادة ═══════════════

@app.route('/command')
@login_required
def command_center():
    bulletins = db_query("SELECT * FROM bulletins ORDER BY id DESC LIMIT 50")

    bulletins_data = [{
        'id': b['id'],
        'title': b['title'],
        'body': b['encrypted_body'],
        'bulletin_type': b['bulletin_type'],
        'priority': b['priority'],
        'author': b['author'],
        'created_at': b['created_at'],
    } for b in bulletins]

    stats = {
        'total_officers': db_query("SELECT COUNT(*) as c FROM users", one=True)['c'],
        'active_cases': db_query("SELECT COUNT(*) as c FROM cases WHERE status='OPEN'", one=True)['c'],
        'critical_cases': db_query("SELECT COUNT(*) as c FROM cases WHERE priority='CRITICAL'", one=True)['c'],
        'total_bulletins': db_query("SELECT COUNT(*) as c FROM bulletins", one=True)['c'],
    }

    return render_template('command.html', bulletins=bulletins_data, stats=stats)


@app.route('/command/bulletin/add', methods=['POST'])
@login_required
def command_add_bulletin():
    if not session.get('is_admin') and session.get('rank') not in (
        'Captain', 'Major', 'Lieutenant Colonel', 'Colonel',
        'Brigadier General', 'Major General', 'Lieutenant General', 'General'
    ):
        flash('غير مصرح', 'danger')
        return redirect(url_for('command_center'))

    title = sanitize(request.form.get('title', ''), 200)
    body = sanitize(request.form.get('body', ''), 5000)

    if not title or not body:
        flash('العنوان والمحتوى مطلوبان', 'danger')
        return redirect(url_for('command_center'))

    db_query(
        """INSERT INTO bulletins (title, encrypted_body, bulletin_type, priority, author)
           VALUES (?, ?, ?, ?, ?)""",
        (title, body,
         request.form.get('bulletin_type', 'order'),
         request.form.get('priority', 'NORMAL'),
         session['user']),
        commit=True
    )

    log_activity(session['user'], 'نشر تعميم', title)

    all_users = db_query("SELECT username FROM users")
    for u in all_users:
        if u['username'] != session['user']:
            create_notification(
                u['username'],
                'تعميم جديد 📢',
                title,
                '📢',
                url_for('command_center')
            )

    flash('تم نشر التعميم', 'success')
    return redirect(url_for('command_center'))


@app.route('/command/bulletin/<int:bulletin_id>/delete')
@login_required
@admin_required
def command_delete_bulletin(bulletin_id):
    db_query("DELETE FROM bulletins WHERE id=?", (bulletin_id,), commit=True)
    log_activity(session['user'], 'حذف تعميم', f'#{bulletin_id}')
    flash('تم الحذف', 'success')
    return redirect(url_for('command_center'))


# ═══════════════ MDT - Mobile Data Terminal ═══════════════

@app.route('/mdt')
@login_required
def mdt():
    return render_template('mdt.html')


# ─── الأشخاص ───

@app.route('/mdt/citizens')
@login_required
def mdt_citizens():
    q = sanitize(request.args.get('q', ''), 100)

    if q:
        rows = db_query(
            """SELECT * FROM citizens
               WHERE full_name LIKE ?
               ORDER BY id DESC LIMIT 50""",
            (f'%{q}%',)
        )
    else:
        rows = db_query("SELECT * FROM citizens ORDER BY id DESC LIMIT 50")

    citizens = [dict(r) for r in rows]

    for c in citizens:
        wanted = db_query(
            "SELECT id FROM wanted WHERE full_name=? AND status='WANTED'",
            (c['full_name'],), one=True
        )
        c['is_wanted'] = bool(wanted)

    return render_template('mdt_citizens.html', citizens=citizens, query=q)


@app.route('/mdt/citizens/add', methods=['POST'])
@login_required
def mdt_citizen_add():
    full_name = sanitize(request.form.get('full_name', ''), 100)
    if not full_name:
        flash('الاسم مطلوب', 'danger')
        return redirect(url_for('mdt_citizens'))

    image_filename = None
    file = request.files.get('image')
    if file and file.filename:
        if allowed_file(file.filename):
            file.seek(0, 2)
            size = file.tell()
            file.seek(0)
            if size > 5 * 1024 * 1024:
                flash('حجم الصورة كبير (الحد 5 ميجا)', 'danger')
                return redirect(url_for('mdt_citizens'))

            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_name = f"{int(datetime.now().timestamp())}_{random.randint(1000,9999)}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
            image_filename = unique_name
        else:
            flash('نوع الصورة غير مسموح', 'danger')
            return redirect(url_for('mdt_citizens'))

    try:
        db_query(
            """INSERT INTO citizens
               (full_name, phone, license_status, weapon_license,
                criminal_record, status, notes, image, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                full_name,
                sanitize(request.form.get('phone', ''), 30),
                request.form.get('license_status', 'VALID'),
                request.form.get('weapon_license', 'NONE'),
                sanitize(request.form.get('criminal_record', ''), 2000),
                request.form.get('status', 'CLEAN'),
                sanitize(request.form.get('notes', ''), 1000),
                image_filename,
                session['user']
            ),
            commit=True
        )
        log_activity(session['user'], 'إضافة مواطن', full_name)
        flash(f'تم إضافة {full_name}', 'success')
    except Exception as e:
        print(f"خطأ: {e}")
        flash('حدث خطأ', 'danger')

    return redirect(url_for('mdt_citizens'))


@app.route('/mdt/citizens/<int:cid>')
@login_required
def mdt_citizen_detail(cid):
    citizen = db_query("SELECT * FROM citizens WHERE id=?", (cid,), one=True)
    if not citizen:
        flash('الشخص غير موجود', 'danger')
        return redirect(url_for('mdt_citizens'))

    wanted = db_query(
        "SELECT * FROM wanted WHERE full_name=? AND status='WANTED'",
        (citizen['full_name'],), one=True
    )

    tickets = db_query(
        "SELECT * FROM tickets WHERE person_name=? ORDER BY id DESC",
        (citizen['full_name'],)
    )

    return render_template('mdt_citizen_detail.html',
                          citizen=dict(citizen),
                          wanted=dict(wanted) if wanted else None,
                          tickets=[dict(t) for t in tickets])


@app.route('/mdt/citizens/<int:cid>/delete')
@login_required
def mdt_citizen_delete(cid):
    if not can_delete():
        flash('غير مصرح - الحذف متاح للرتب العليا فقط', 'danger')
        return redirect(url_for('mdt_citizens'))

    row = db_query("SELECT image FROM citizens WHERE id=?", (cid,), one=True)
    if row and row['image']:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], row['image']))
        except:
            pass

    db_query("DELETE FROM citizens WHERE id=?", (cid,), commit=True)
    log_activity(session['user'], 'حذف مواطن', f'#{cid}')
    flash('تم حذف الشخص', 'success')
    return redirect(url_for('mdt_citizens'))


# ─── المركبات ───

@app.route('/mdt/vehicles')
@login_required
def mdt_vehicles():
    q = sanitize(request.args.get('q', ''), 100)

    if q:
        rows = db_query(
            """SELECT * FROM vehicles
               WHERE plate LIKE ? OR owner_name LIKE ? OR model LIKE ?
               ORDER BY id DESC LIMIT 50""",
            (f'%{q}%', f'%{q}%', f'%{q}%')
        )
    else:
        rows = db_query("SELECT * FROM vehicles ORDER BY id DESC LIMIT 50")

    return render_template('mdt_vehicles.html',
                          vehicles=[dict(r) for r in rows],
                          query=q)


@app.route('/mdt/vehicles/add', methods=['POST'])
@login_required
def mdt_vehicle_add():
    plate = sanitize(request.form.get('plate', ''), 20).upper()
    if not plate:
        flash('رقم اللوحة مطلوب', 'danger')
        return redirect(url_for('mdt_vehicles'))

    try:
        db_query(
            """INSERT INTO vehicles
               (plate, model, color, owner_name, registration_status,
                insurance_status, status, notes, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                plate,
                sanitize(request.form.get('model', ''), 100),
                sanitize(request.form.get('color', ''), 50),
                sanitize(request.form.get('owner_name', ''), 100),
                request.form.get('registration_status', 'VALID'),
                request.form.get('insurance_status', 'VALID'),
                request.form.get('status', 'CLEAN'),
                sanitize(request.form.get('notes', ''), 1000),
                session['user']
            ),
            commit=True
        )
        log_activity(session['user'], 'إضافة مركبة', plate)
        flash(f'تم إضافة المركبة {plate}', 'success')
    except Exception:
        flash('رقم اللوحة مستخدم بالفعل', 'danger')

    return redirect(url_for('mdt_vehicles'))


@app.route('/mdt/vehicles/<int:vid>/delete')
@login_required
def mdt_vehicle_delete(vid):
    if not can_delete():
        flash('غير مصرح - الحذف متاح للرتب العليا فقط', 'danger')
        return redirect(url_for('mdt_vehicles'))

    db_query("DELETE FROM vehicles WHERE id=?", (vid,), commit=True)
    log_activity(session['user'], 'حذف مركبة', f'#{vid}')
    flash('تم حذف المركبة', 'success')
    return redirect(url_for('mdt_vehicles'))


# ─── البلاغات ───

@app.route('/mdt/calls')
@login_required
def mdt_calls():
    status_filter = request.args.get('status', 'ALL')

    query = "SELECT * FROM calls"
    params = []

    if status_filter in ('OPEN', 'IN_PROGRESS', 'CLOSED'):
        query += " WHERE status=?"
        params.append(status_filter)

    query += " ORDER BY id DESC LIMIT 100"

    rows = db_query(query, params)
    calls = [dict(r) for r in rows]

    stats = {
        'open': db_query("SELECT COUNT(*) as c FROM calls WHERE status='OPEN'", one=True)['c'],
        'in_progress': db_query("SELECT COUNT(*) as c FROM calls WHERE status='IN_PROGRESS'", one=True)['c'],
        'closed': db_query("SELECT COUNT(*) as c FROM calls WHERE status='CLOSED'", one=True)['c'],
    }

    return render_template('mdt_calls.html',
                          calls=calls,
                          stats=stats,
                          status_filter=status_filter)


@app.route('/mdt/calls/add', methods=['POST'])
@login_required
def mdt_call_add():
    location = sanitize(request.form.get('location', ''), 200)
    description = sanitize(request.form.get('description', ''), 2000)

    if not location or not description:
        flash('الموقع والوصف مطلوبان', 'danger')
        return redirect(url_for('mdt_calls'))

    call_number = f"CALL-{datetime.now().year}-{random.randint(1000, 9999)}"

    db_query(
        """INSERT INTO calls
           (call_number, caller_name, location, description, call_type,
            priority, status, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            call_number,
            sanitize(request.form.get('caller_name', ''), 100),
            location,
            description,
            request.form.get('call_type', 'GENERAL'),
            request.form.get('priority', 'MEDIUM'),
            'OPEN',
            session['user']
        ),
        commit=True
    )

    log_activity(session['user'], 'بلاغ جديد', f'{call_number}: {location}')

    all_users = db_query("SELECT username FROM users WHERE is_admin=1")
    for u in all_users:
        if u['username'] != session['user']:
            create_notification(
                u['username'],
                'بلاغ جديد 🚨',
                f'{location} - {description[:50]}',
                '🚨',
                url_for('mdt_calls')
            )

    flash(f'تم تسجيل البلاغ: {call_number}', 'success')
    return redirect(url_for('mdt_calls'))


@app.route('/mdt/calls/<int:call_id>/status/<new_status>')
@login_required
def mdt_call_update(call_id, new_status):
    if new_status not in ('OPEN', 'IN_PROGRESS', 'CLOSED'):
        flash('حالة غير صحيحة', 'danger')
        return redirect(url_for('mdt_calls'))

    db_query(
        "UPDATE calls SET status=?, assigned_to=? WHERE id=?",
        (new_status, session['user'], call_id),
        commit=True
    )
    log_activity(session['user'], 'تحديث بلاغ', f'#{call_id} → {new_status}')
    flash('تم تحديث البلاغ', 'success')
    return redirect(url_for('mdt_calls'))


@app.route('/mdt/calls/<int:call_id>/delete')
@login_required
def mdt_call_delete(call_id):
    if not can_delete():
        flash('غير مصرح - الحذف متاح للرتب العليا فقط', 'danger')
        return redirect(url_for('mdt_calls'))

    db_query("DELETE FROM calls WHERE id=?", (call_id,), commit=True)
    log_activity(session['user'], 'حذف بلاغ', f'#{call_id}')
    flash('تم حذف البلاغ', 'success')
    return redirect(url_for('mdt_calls'))


# ─── المخالفات ───

@app.route('/mdt/tickets')
@login_required
def mdt_tickets():
    rows = db_query("SELECT * FROM tickets ORDER BY id DESC LIMIT 100")
    return render_template('mdt_tickets.html',
                          tickets=[dict(r) for r in rows])


@app.route('/mdt/tickets/add', methods=['POST'])
@login_required
def mdt_ticket_add():
    person = sanitize(request.form.get('person_name', ''), 100)
    violation = sanitize(request.form.get('violation', ''), 500)

    if not person or not violation:
        flash('الاسم والمخالفة مطلوبان', 'danger')
        return redirect(url_for('mdt_tickets'))

    ticket_number = f"TKT-{datetime.now().year}-{random.randint(1000, 9999)}"

    try:
        fine = float(request.form.get('fine_amount', 0))
    except:
        fine = 0

    db_query(
        """INSERT INTO tickets
           (ticket_number, person_name, vehicle_plate, violation,
            fine_amount, issued_by, status)
           VALUES (?, ?, ?, ?, ?, ?, 'UNPAID')""",
        (ticket_number, person,
         sanitize(request.form.get('vehicle_plate', ''), 20),
         violation, fine, session['user']),
        commit=True
    )
    log_activity(session['user'], 'مخالفة جديدة', f'{ticket_number}: {person}')
    flash(f'تم إصدار المخالفة: {ticket_number}', 'success')
    return redirect(url_for('mdt_tickets'))


@app.route('/mdt/tickets/<int:tid>/delete')
@login_required
def mdt_ticket_delete(tid):
    if not can_delete():
        flash('غير مصرح - الحذف متاح للرتب العليا فقط', 'danger')
        return redirect(url_for('mdt_tickets'))

    db_query("DELETE FROM tickets WHERE id=?", (tid,), commit=True)
    log_activity(session['user'], 'حذف مخالفة', f'#{tid}')
    flash('تم حذف المخالفة', 'success')
    return redirect(url_for('mdt_tickets'))


# ─── المطلوبين ───

@app.route('/mdt/wanted')
@login_required
def mdt_wanted():
    rows = db_query(
        "SELECT * FROM wanted WHERE status='WANTED' ORDER BY id DESC"
    )
    return render_template('mdt_wanted.html',
                          wanted=[dict(r) for r in rows])


@app.route('/mdt/wanted/add', methods=['POST'])
@login_required
def mdt_wanted_add():
    full_name = sanitize(request.form.get('full_name', ''), 100)
    crime = sanitize(request.form.get('crime', ''), 500)

    if not full_name or not crime:
        flash('الاسم والجريمة مطلوبان', 'danger')
        return redirect(url_for('mdt_wanted'))

    try:
        reward = float(request.form.get('reward', 0))
    except:
        reward = 0

    db_query(
        """INSERT INTO wanted
           (full_name, crime, danger_level, reward, status, notes, created_by)
           VALUES (?, ?, ?, ?, 'WANTED', ?, ?)""",
        (full_name, crime,
         request.form.get('danger_level', 'MEDIUM'),
         reward,
         sanitize(request.form.get('notes', ''), 1000),
         session['user']),
        commit=True
    )
    log_activity(session['user'], 'إضافة مطلوب', full_name)
    flash(f'تم إضافة {full_name} للمطلوبين', 'success')
    return redirect(url_for('mdt_wanted'))


@app.route('/mdt/wanted/<int:wid>/capture')
@login_required
def mdt_wanted_capture(wid):
    db_query("UPDATE wanted SET status='CAPTURED' WHERE id=?", (wid,), commit=True)
    log_activity(session['user'], 'القبض على مطلوب', f'#{wid}')
    flash('تم تسجيل القبض', 'success')
    return redirect(url_for('mdt_wanted'))


@app.route('/mdt/wanted/<int:wid>/delete')
@login_required
def mdt_wanted_delete(wid):
    if not can_delete():
        flash('غير مصرح - الحذف متاح للرتب العليا فقط', 'danger')
        return redirect(url_for('mdt_wanted'))

    db_query("DELETE FROM wanted WHERE id=?", (wid,), commit=True)
    log_activity(session['user'], 'حذف مطلوب', f'#{wid}')
    flash('تم حذف المطلوب', 'success')
    return redirect(url_for('mdt_wanted'))


# ─── بحث سريع ───

@app.route('/mdt/search')
@login_required
def mdt_search():
    q = sanitize(request.args.get('q', ''), 100)

    if not q:
        return jsonify({'citizens': [], 'vehicles': []})

    citizens = db_query(
        """SELECT id, full_name, phone, status FROM citizens
           WHERE full_name LIKE ?
           LIMIT 10""",
        (f'%{q}%',)
    )

    vehicles = db_query(
        """SELECT id, plate, model, owner_name, status FROM vehicles
           WHERE plate LIKE ? OR owner_name LIKE ?
           LIMIT 10""",
        (f'%{q}%', f'%{q}%')
    )

    return jsonify({
        'citizens': [dict(c) for c in citizens],
        'vehicles': [dict(v) for v in vehicles]
    })


# ═══════════════ 🔔 الإشعارات ═══════════════

@app.route('/api/notifications')
@login_required
def api_notifications():
    me = session['user']

    notifications = db_query(
        """SELECT * FROM notifications
           WHERE user=?
           ORDER BY id DESC LIMIT 20""",
        (me,)
    )

    unread_count = db_query(
        "SELECT COUNT(*) as c FROM notifications WHERE user=? AND is_read=0",
        (me,), one=True
    )['c']

    return jsonify({
        'unread': unread_count,
        'notifications': [{
            'id': n['id'],
            'title': n['title'],
            'message': n['message'],
            'icon': n['icon'],
            'link': n['link'],
            'is_read': bool(n['is_read']),
            'created_at': n['created_at']
        } for n in notifications]
    })


@app.route('/notifications/read/<int:nid>')
@login_required
def notification_read(nid):
    db_query(
        "UPDATE notifications SET is_read=1 WHERE id=? AND user=?",
        (nid, session['user']),
        commit=True
    )
    return jsonify({'status': 'ok'})


@app.route('/notifications/read-all')
@login_required
def notifications_read_all():
    db_query(
        "UPDATE notifications SET is_read=1 WHERE user=?",
        (session['user'],),
        commit=True
    )
    flash('تم تعليم الكل كمقروء', 'success')
    return redirect(request.referrer or url_for('dashboard'))


# ═══════════════ 👤 البروفايل ═══════════════

@app.route('/profile')
@login_required
def profile():
    user = db_query("SELECT * FROM users WHERE username=?", (session['user'],), one=True)
    if not user:
        flash('مستخدم غير موجود', 'danger')
        return redirect(url_for('dashboard'))

    stats = {
        'messages_sent': db_query("SELECT COUNT(*) as c FROM messages WHERE sender=?", (session['user'],), one=True)['c'],
        'cases_created': db_query("SELECT COUNT(*) as c FROM cases WHERE lead_officer=?", (session['user'],), one=True)['c'],
        'infos_created': db_query("SELECT COUNT(*) as c FROM infos WHERE author=?", (session['user'],), one=True)['c'],
        'tickets_issued': db_query("SELECT COUNT(*) as c FROM tickets WHERE issued_by=?", (session['user'],), one=True)['c'],
    }

    activities = db_query("SELECT * FROM activity_log WHERE user=? ORDER BY id DESC LIMIT 10", (session['user'],))
    
    achievements = db_query("""
        SELECT a.*, ua.created_at as earned_at 
        FROM achievements a 
        JOIN user_achievements ua ON a.id = ua.achievement_id 
        WHERE ua.user = ? 
        ORDER BY ua.created_at DESC
    """, (session['user'],))

    next_rank = None
    next_req = None
    current_index = ALL_RANKS.index(user['rank']) if user['rank'] in ALL_RANKS else -1
    if current_index >= 0 and current_index < len(ALL_RANKS) - 1:
        next_rank = ALL_RANKS[current_index + 1]
        next_req = RANK_REQUIREMENTS.get(next_rank)

    return render_template('profile.html',
                          user=dict(user),
                          stats=stats,
                          activities=[dict(a) for a in activities],
                          achievements=[dict(a) for a in achievements],
                          next_rank=next_rank,
                          next_req=next_req,
                          current_points=user['points'])


@app.route('/profile/update', methods=['POST'])
@login_required
def profile_update():
    bio = sanitize(request.form.get('bio', ''), 500)
    phone = sanitize(request.form.get('phone', ''), 30)

    file = request.files.get('image')
    if file and file.filename:
        if allowed_file(file.filename):
            file.seek(0, 2)
            size = file.tell()
            file.seek(0)
            if size > 5 * 1024 * 1024:
                flash('حجم الصورة كبير (الحد 5 ميجا)', 'danger')
                return redirect(url_for('profile'))

            old = db_query("SELECT image FROM users WHERE username=?", (session['user'],), one=True)
            if old and old['image']:
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], old['image']))
                except:
                    pass

            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_name = f"profile_{session['user']}_{int(datetime.now().timestamp())}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))

            db_query("UPDATE users SET image=? WHERE username=?", (unique_name, session['user']), commit=True)
        else:
            flash('نوع الصورة غير مسموح', 'danger')
            return redirect(url_for('profile'))

    db_query("UPDATE users SET bio=?, phone=? WHERE username=?", (bio, phone, session['user']), commit=True)
    log_activity(session['user'], 'تحديث البروفايل', '')
    flash('تم تحديث البروفايل', 'success')
    return redirect(url_for('profile'))


@app.route('/profile/change-password', methods=['POST'])
@login_required
def profile_change_password():
    old_password = request.form.get('old_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    if not old_password or not new_password or not confirm_password:
        flash('جميع الحقول مطلوبة', 'danger')
        return redirect(url_for('profile'))

    if new_password != confirm_password:
        flash('كلمتا المرور غير متطابقتين', 'danger')
        return redirect(url_for('profile'))

    if len(new_password) < 6:
        flash('كلمة المرور 6 أحرف على الأقل', 'danger')
        return redirect(url_for('profile'))

    user = db_query("SELECT password_hash FROM users WHERE username=?", (session['user'],), one=True)

    if not check_password_hash(user['password_hash'], old_password):
        flash('كلمة المرور الحالية غير صحيحة', 'danger')
        return redirect(url_for('profile'))

    db_query("UPDATE users SET password_hash=? WHERE username=?", (generate_password_hash(new_password), session['user']), commit=True)
    log_activity(session['user'], 'تغيير كلمة المرور', '')

    create_notification(
        session['user'],
        'تم تغيير كلمة المرور 🔐',
        'تم تغيير كلمة مرورك بنجاح',
        '🔐',
        url_for('profile')
    )

    flash('تم تغيير كلمة المرور', 'success')
    return redirect(url_for('profile'))


# ═══════════════ 📋 سجل النشاط ═══════════════

@app.route('/activity')
@login_required
def activity_log():
    if session.get('rank') not in DELETE_ALLOWED_RANKS:
        flash('سجل النشاط متاح للرتب العليا فقط', 'danger')
        return redirect(url_for('dashboard'))

    user_filter = request.args.get('user', 'ALL')

    if user_filter == 'ALL':
        rows = db_query("SELECT * FROM activity_log ORDER BY id DESC LIMIT 200")
    else:
        rows = db_query("SELECT * FROM activity_log WHERE user=? ORDER BY id DESC LIMIT 200", (user_filter,))

    activities = [dict(r) for r in rows]
    users = db_query("SELECT DISTINCT user FROM activity_log ORDER BY user")

    return render_template('activity_log.html', activities=activities, users=[u['user'] for u in users], user_filter=user_filter)


# ═══════════════ 📅 الشيفتات ═══════════════

@app.route('/duty')
@login_required
def duty_roster():
    officers = db_query(
        """SELECT d.*, u.badge, u.image
           FROM duty_roster d
           LEFT JOIN users u ON d.officer = u.username
           ORDER BY 
             CASE d.status 
               WHEN 'ON_DUTY' THEN 1
               WHEN 'BUSY' THEN 2
               WHEN 'BREAK' THEN 3
               ELSE 4
             END,
             d.rank"""
    )

    stats = {
        'on_duty': db_query("SELECT COUNT(*) as c FROM duty_roster WHERE status='ON_DUTY'", one=True)['c'],
        'busy': db_query("SELECT COUNT(*) as c FROM duty_roster WHERE status='BUSY'", one=True)['c'],
        'break': db_query("SELECT COUNT(*) as c FROM duty_roster WHERE status='BREAK'", one=True)['c'],
        'off_duty': db_query("SELECT COUNT(*) as c FROM duty_roster WHERE status='OFF_DUTY'", one=True)['c'],
    }

    return render_template('duty_roster.html', officers=[dict(o) for o in officers], stats=stats)


@app.route('/duty/status/<new_status>')
@login_required
def duty_update_status(new_status):
    if new_status not in ('ON_DUTY', 'BUSY', 'BREAK', 'OFF_DUTY'):
        flash('حالة غير صحيحة', 'danger')
        return redirect(url_for('duty_roster'))

    me = session['user']
    existing = db_query("SELECT id FROM duty_roster WHERE officer=?", (me,), one=True)

    if existing:
        db_query("UPDATE duty_roster SET status=?, shift_start=?, updated_at=CURRENT_TIMESTAMP WHERE officer=?", (new_status, datetime.now().strftime('%H:%M') if new_status == 'ON_DUTY' else None, me), commit=True)
    else:
        db_query("INSERT INTO duty_roster (officer, rank, status, shift_start) VALUES (?, ?, ?, ?)", (me, session.get('rank'), new_status, datetime.now().strftime('%H:%M') if new_status == 'ON_DUTY' else None), commit=True)

    log_activity(me, 'تحديث الشيفت', f'الحالة: {new_status}')
    flash('تم تحديث حالتك', 'success')
    return redirect(url_for('duty_roster'))


# ═══════════════ 🤖 AI Assistant ═══════════════

@app.route('/ai/ask', methods=['POST'])
@login_required
def ai_ask():
    data = request.get_json() or {}
    question = sanitize(data.get('question', ''), 500)

    if not question:
        return jsonify({'answer': 'اكتب سؤالك أولاً.'})

    try:
        answer = answer_question(question)
    except Exception as e:
        print(f"AI Error: {e}")
        answer = '❌ حصل خطأ، حاول تاني.'

    log_activity(session['user'], 'سؤال AI', question[:100])
    return jsonify({'answer': answer})


# ═══════════════ SocketIO ═══════════════

@socketio.on('connect')
def on_connect():
    print(f"🔌 متصل: {request.sid}")


@socketio.on('disconnect')
def on_disconnect():
    print(f"❌ انقطع: {request.sid}")


@socketio.on('join')
def on_join(data):
    user = data.get('user')
    other = data.get('other')

    if not user or not other:
        return

    if user != session.get('user'):
        return

    user_row = db_query("SELECT rank FROM users WHERE username=?", (user,), one=True)
    if not user_row or not can_chat(user_row['rank']):
        return

    other_row = db_query("SELECT rank FROM users WHERE username=?", (other,), one=True)
    if not other_row or not can_chat(other_row['rank']):
        return

    pair_room = f"pair_{min(user, other)}_{max(user, other)}"
    join_room(pair_room)

    rows = db_query("SELECT * FROM messages WHERE (sender=? AND receiver=?) OR (sender=? AND receiver=?) ORDER BY id DESC LIMIT 100", (user, other, other, user))

    for r in reversed(rows):
        emit('new_message', {
            'sender': r['sender'],
            'receiver': r['receiver'],
            'encrypted': r['encrypted'],
            'time': r['created_at']
        })


@socketio.on('send_message')
def on_send(data):
    sender = data.get('sender')
    receiver = data.get('receiver')
    encrypted = data.get('encrypted')

    if not all([sender, receiver, encrypted]):
        return

    if sender != session.get('user'):
        return

    encrypted = str(encrypted)[:5000]

    sender_row = db_query("SELECT rank FROM users WHERE username=?", (sender,), one=True)
    if not sender_row or not can_chat(sender_row['rank']):
        return

    receiver_row = db_query("SELECT rank FROM users WHERE username=?", (receiver,), one=True)
    if not receiver_row or not can_chat(receiver_row['rank']):
        return

    db_query("INSERT INTO messages (sender, receiver, encrypted, room) VALUES (?, ?, ?, ?)", (sender, receiver, encrypted, 'general'), commit=True)

    payload = {
        'sender': sender,
        'receiver': receiver,
        'encrypted': encrypted,
        'time': datetime.now().strftime('%H:%M')
    }

    pair_room = f"pair_{min(sender, receiver)}_{max(sender, receiver)}"
    emit('new_message', payload, room=pair_room)


# ═══════════════ التشغيل ═══════════════

if __name__ == '__main__':
    init_db()
    print("=" * 60)
    print("  🛡️  LSPD Server Started")
    print("  🌐  http://localhost:5000")
    print("=" * 60)
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)