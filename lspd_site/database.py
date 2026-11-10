"""قاعدة البيانات"""

import sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = 'lspd.db'

SEED_USERS = [
    ("general",     "gen123",    "LSPD-001", "General",            1),
    ("ltgeneral",   "ltg123",    "LSPD-002", "Lieutenant General", 1),
    ("majgeneral",  "mjg123",    "LSPD-003", "Major General",      1),
    ("brigadier",   "brg123",    "LSPD-004", "Brigadier General",  1),
    ("colonel",     "col123",    "LSPD-005", "Colonel",            1),
    ("ltcolonel",   "ltc123",    "LSPD-006", "Lieutenant Colonel", 0),
    ("major",       "maj123",    "LSPD-007", "Major",              0),
    ("captain",     "capt123",   "LSPD-008", "Captain",            0),
    ("firstlt",     "flt123",    "LSPD-009", "First Lieutenant",   0),
    ("lieutenant",  "lt123",     "LSPD-010", "Lieutenant",         0),
    ("staffsgt",    "ssg123",    "LSPD-011", "Staff Sergeant",     0),
    ("firstsgt",    "fsg123",    "LSPD-012", "First Sergeant",     0),
    ("sergeant",    "sgt123",    "LSPD-013", "Sergeant",           0),
    ("seniorlead",  "slo123",    "LSPD-014", "Senior Lead Officer",0),
    ("senior",      "sen123",    "LSPD-015", "Senior Officer",     0),
    ("officer3",    "off3",      "LSPD-016", "Officer 3",          0),
    ("officer2",    "off2",      "LSPD-017", "Officer 2",          0),
    ("officer1",    "off1",      "LSPD-018", "Officer 1",          0),
    ("solocadet",   "sol123",    "LSPD-019", "Solo Cadet",         0),
    ("cadet",       "cdt123",    "LSPD-020", "Cadet",              0),
]

def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # ─── USERS (ضفنا points + wings) ───
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            badge TEXT UNIQUE NOT NULL,
            rank TEXT DEFAULT 'Officer 1',
            is_admin INTEGER DEFAULT 0,
            points INTEGER DEFAULT 0,
            wings TEXT DEFAULT '',
            image TEXT,
            bio TEXT,
            phone TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            encrypted TEXT NOT NULL,
            room TEXT DEFAULT 'general',
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS infos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            encrypted_body TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            classification TEXT DEFAULT 'CONFIDENTIAL',
            author TEXT,
            image TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_number TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            encrypted_description TEXT NOT NULL,
            suspect TEXT,
            status TEXT DEFAULT 'OPEN',
            priority TEXT DEFAULT 'MEDIUM',
            lead_officer TEXT,
            location TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            encrypted_content TEXT NOT NULL,
            evidence_type TEXT DEFAULT 'physical',
            image TEXT,
            added_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS bulletins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            encrypted_body TEXT NOT NULL,
            bulletin_type TEXT DEFAULT 'order',
            priority TEXT DEFAULT 'NORMAL',
            author TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ═══════ جداول MDT ═══════
    cur.execute("""
        CREATE TABLE IF NOT EXISTS citizens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            phone TEXT,
            license_status TEXT DEFAULT 'VALID',
            weapon_license TEXT DEFAULT 'NONE',
            criminal_record TEXT,
            status TEXT DEFAULT 'CLEAN',
            notes TEXT,
            image TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate TEXT UNIQUE NOT NULL,
            model TEXT,
            color TEXT,
            owner_name TEXT,
            registration_status TEXT DEFAULT 'VALID',
            insurance_status TEXT DEFAULT 'VALID',
            status TEXT DEFAULT 'CLEAN',
            notes TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_number TEXT UNIQUE,
            caller_name TEXT,
            location TEXT,
            description TEXT,
            call_type TEXT DEFAULT 'GENERAL',
            priority TEXT DEFAULT 'MEDIUM',
            status TEXT DEFAULT 'OPEN',
            assigned_to TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_number TEXT UNIQUE,
            person_name TEXT,
            vehicle_plate TEXT,
            violation TEXT,
            fine_amount REAL DEFAULT 0,
            issued_by TEXT,
            status TEXT DEFAULT 'UNPAID',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS wanted (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            crime TEXT,
            danger_level TEXT DEFAULT 'MEDIUM',
            reward REAL DEFAULT 0,
            status TEXT DEFAULT 'WANTED',
            notes TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ═══════ جداول إضافية ═══════
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT,
            icon TEXT DEFAULT '🔔',
            link TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            ip TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS duty_roster (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            officer TEXT UNIQUE NOT NULL,
            rank TEXT,
            status TEXT DEFAULT 'OFF_DUTY',
            shift_start TEXT,
            location TEXT,
            notes TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 🆕 الأوسمة (Achievements)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            icon TEXT DEFAULT '🏆',
            points_reward INTEGER DEFAULT 0
        )
    """)

    # 🆕 أوسمة الضباط
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            achievement_id INTEGER NOT NULL,
            awarded_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (achievement_id) REFERENCES achievements(id) ON DELETE CASCADE
        )
    """)

    # 🆕 سجل النقاط
    cur.execute("""
        CREATE TABLE IF NOT EXISTS points_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            amount INTEGER NOT NULL,
            reason TEXT,
            given_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 🆕 الـ Wings
    cur.execute("""
        CREATE TABLE IF NOT EXISTS wings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            icon TEXT DEFAULT '🪽'
        )
    """)

    # إضافة الـ Wings الافتراضية
    default_wings = [
        ('Air Wing', 'الجناح الجوي', '🚁'),
        ('K9 Wing', 'وحدة الكلاب', '🐕'),
        ('SWAT Wing', 'وحدة التدخل السريع', '🛡️'),
        ('Traffic Wing', 'المرور', '🚦'),
        ('Investigation Wing', 'التحقيق', '🔍'),
        ('Cyber Wing', 'الأمن السيبراني', '💻'),
        ('Marine Wing', 'الوحدة البحرية', '⛵'),
    ]
    for w_name, w_desc, w_icon in default_wings:
        cur.execute("INSERT OR IGNORE INTO wings (name, description, icon) VALUES (?, ?, ?)", (w_name, w_desc, w_icon))

    # إضافة الأوسمة الافتراضية
    default_achievements = [
        ('Officer of the Month', 'ضابط الشهر', '🌟', 100),
        ('Bravery Medal', 'وسام الشجاعة', '🎖️', 200),
        ('Perfect Attendance', 'حضور مثالي', '📅', 50),
        ('Top Investigator', 'أفضل محقق', '🕵️', 150),
        ('First Arrest', 'أول عملية قبض', '🚔', 25),
        ('100 Cases Solved', 'حل 100 قضية', '💯', 500),
    ]
    for a_name, a_desc, a_icon, a_reward in default_achievements:
        cur.execute("INSERT OR IGNORE INTO achievements (name, description, icon, points_reward) VALUES (?, ?, ?, ?)", (a_name, a_desc, a_icon, a_reward))

    con.commit()

    for username, password, badge, rank, is_admin in SEED_USERS:
        cur.execute("SELECT id FROM users WHERE username=? OR badge=?", (username, badge))
        if not cur.fetchone():
            try:
                cur.execute(
                    """INSERT INTO users (username, password_hash, badge, rank, is_admin)
                       VALUES (?, ?, ?, ?, ?)""",
                    (username, generate_password_hash(password), badge, rank, is_admin)
                )
            except sqlite3.IntegrityError:
                pass

    con.commit()
    con.close()


def db_query(sql, params=(), one=False, commit=False):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(sql, params)

    if commit:
        con.commit()
        result = cur.lastrowid
        con.close()
        return result

    rows = cur.fetchone() if one else cur.fetchall()
    con.close()
    return rows