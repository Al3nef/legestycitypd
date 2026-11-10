"""LSPD - AI Assistant
   مساعد ذكي محلي (بدون API خارجي)
"""

import re
from database import db_query


def detect_intent(question):
    """يحلل السؤال ويرجع النية"""
    q = question.lower().strip()

    # ── إحصائيات عامة ──
    if any(w in q for w in ['عدد الضباط', 'كم ضابط', 'الضباط', 'police officers', 'officers count']):
        return 'count_officers'

    if any(w in q for w in ['عدد القضايا', 'كم قضية', 'cases count', 'how many cases']):
        return 'count_cases'

    if any(w in q for w in ['قضايا مفتوحة', 'open cases']):
        return 'open_cases'

    if any(w in q for w in ['قضايا مغلقة', 'closed cases']):
        return 'closed_cases'

    if any(w in q for w in ['بلاغات', 'بلاغ', 'calls', '911']):
        return 'count_calls'

    if any(w in q for w in ['مطلوبين', 'مطلوب', 'wanted']):
        return 'count_wanted'

    if any(w in q for w in ['مخالفات', 'مخالفة', 'tickets']):
        return 'count_tickets'

    if any(w in q for w in ['مركبات', 'عربيات', 'مركبة', 'vehicles']):
        return 'count_vehicles'

    if any(w in q for w in ['مواطنين', 'مواطن', 'citizens']):
        return 'count_citizens'

    if any(w in q for w in ['رسائل', 'messages']):
        return 'count_messages'

    # ── الشيفتات ──
    if any(w in q for w in ['في الشيفت', 'شيفت', 'في الخدمة', 'on duty', 'duty']):
        return 'on_duty_list'

    # ── أكثر ضابط نشاط ──
    if any(w in q for w in ['أكثر ضابط', 'أنشط ضابط', 'top officer', 'most active']):
        return 'top_officer'

    # ── معلومات عن شخص ──
    match = re.search(r'(?:عن|عن المواطن|معلومات|بحث)\s+["\']?([\u0600-\u06FF\w\s]+)["\']?', question, re.IGNORECASE)
    if match and any(w in q for w in ['مواطن', 'شخص', 'citizen', 'سجل']):
        return ('search_citizen', match.group(1).strip())

    # ── بحث عن مركبة ──
    match = re.search(r'(?:لوحة|مركبة|سيارة|plate|vehicle)\s+([A-Za-z0-9\-]+)', question, re.IGNORECASE)
    if match:
        return ('search_vehicle', match.group(1).strip().upper())

    # ── آخر القضايا ──
    if any(w in q for w in ['آخر قضية', 'أحدث قضية', 'latest case', 'recent case']):
        return 'latest_case'

    # ── آخر بلاغ ──
    if any(w in q for w in ['آخر بلاغ', 'أحدث بلاغ', 'latest call']):
        return 'latest_call'

    # ── معلومات عن النظام ──
    if any(w in q for w in ['مساعدة', 'help', 'ساعدني', 'إيه اللي تعرفه']):
        return 'help'

    # ── الترحيب ──
    if any(w in q for w in ['أهلا', 'مرحبا', 'السلام', 'هاي', 'hi', 'hello', 'hey']):
        return 'greeting'

    return 'unknown'


def answer_question(question):
    """يرجع الإجابة على السؤال"""
    intent = detect_intent(question)

    # ─── ترحيب ───
    if intent == 'greeting':
        return '👋 أهلاً بيك! أنا مساعد LSPD الذكي. اسألني عن:\n• عدد الضباط\n• القضايا\n• البلاغات\n• المواطنين\n• الشيفتات'

    # ─── مساعدة ───
    if intent == 'help':
        return (
            '🤖 **أقدر أساعدك في:**\n\n'
            '📊 **إحصائيات:**\n'
            '• "كم عدد الضباط؟"\n'
            '• "القضايا المفتوحة كام؟"\n'
            '• "عدد البلاغات"\n\n'
            '🔍 **بحث:**\n'
            '• "معلومات عن [اسم]"\n'
            '• "لوحة [رقم اللوحة]"\n\n'
            '👮 **الشيفتات:**\n'
            '• "مين في الشيفت؟"\n\n'
            '🏆 **الأداء:**\n'
            '• "أكثر ضابط نشاطاً"'
        )

    # ─── عدد الضباط ───
    if intent == 'count_officers':
        count = db_query("SELECT COUNT(*) as c FROM users", one=True)['c']
        admins = db_query("SELECT COUNT(*) as c FROM users WHERE is_admin=1", one=True)['c']
        return f'👮 **إجمالي الضباط:** {count}\n🔑 **الأدمن:** {admins}'

    # ─── عدد القضايا ───
    if intent == 'count_cases':
        total = db_query("SELECT COUNT(*) as c FROM cases", one=True)['c']
        return f'📂 **إجمالي القضايا:** {total}'

    # ─── القضايا المفتوحة ───
    if intent == 'open_cases':
        count = db_query("SELECT COUNT(*) as c FROM cases WHERE status='OPEN'", one=True)['c']
        return f'📂 **القضايا المفتوحة:** {count}'

    # ─── القضايا المغلقة ───
    if intent == 'closed_cases':
        count = db_query("SELECT COUNT(*) as c FROM cases WHERE status='CLOSED'", one=True)['c']
        return f'✅ **القضايا المغلقة:** {count}'

    # ─── البلاغات ───
    if intent == 'count_calls':
        total = db_query("SELECT COUNT(*) as c FROM calls", one=True)['c']
        open_calls = db_query("SELECT COUNT(*) as c FROM calls WHERE status='OPEN'", one=True)['c']
        return f'📞 **إجمالي البلاغات:** {total}\n🚨 **مفتوحة:** {open_calls}'

    # ─── المطلوبين ───
    if intent == 'count_wanted':
        count = db_query("SELECT COUNT(*) as c FROM wanted WHERE status='WANTED'", one=True)['c']
        return f'⚠️ **عدد المطلوبين:** {count}'

    # ─── المخالفات ───
    if intent == 'count_tickets':
        total = db_query("SELECT COUNT(*) as c FROM tickets", one=True)['c']
        unpaid = db_query("SELECT COUNT(*) as c FROM tickets WHERE status='UNPAID'", one=True)['c']
        return f'📝 **إجمالي المخالفات:** {total}\n💰 **غير مدفوعة:** {unpaid}'

    # ─── المركبات ───
    if intent == 'count_vehicles':
        count = db_query("SELECT COUNT(*) as c FROM vehicles", one=True)['c']
        return f'🚗 **عدد المركبات:** {count}'

    # ─── المواطنين ───
    if intent == 'count_citizens':
        count = db_query("SELECT COUNT(*) as c FROM citizens", one=True)['c']
        return f'👥 **عدد المواطنين:** {count}'

    # ─── الرسائل ───
    if intent == 'count_messages':
        count = db_query("SELECT COUNT(*) as c FROM messages", one=True)['c']
        return f'💬 **عدد الرسائل:** {count}'

    # ─── قائمة الشيفت ───
    if intent == 'on_duty_list':
        rows = db_query(
            "SELECT * FROM duty_roster WHERE status IN ('ON_DUTY', 'BUSY') ORDER BY status"
        )
        if not rows:
            return '📅 **لا يوجد ضباط في الشيفت حالياً.**'
        lines = ['👮 **الضباط في الشيفت:**\n']
        for r in rows:
            emoji = '🟢' if r['status'] == 'ON_DUTY' else '🟡'
            lines.append(f'{emoji} **{r["officer"]}** — {r["rank"] or ""}')
        return '\n'.join(lines)

    # ─── آخر قضية ───
    if intent == 'latest_case':
        row = db_query("SELECT * FROM cases ORDER BY id DESC LIMIT 1", one=True)
        if not row:
            return '📂 **لا يوجد قضايا بعد.**'
        return (
            f'📂 **آخر قضية:**\n\n'
            f'**رقم:** {row["case_number"]}\n'
            f'**العنوان:** {row["title"]}\n'
            f'**الحالة:** {row["status"]}\n'
            f'**الأولوية:** {row["priority"]}\n'
            f'**الضابط:** {row["lead_officer"]}'
        )

    # ─── آخر بلاغ ───
    if intent == 'latest_call':
        row = db_query("SELECT * FROM calls ORDER BY id DESC LIMIT 1", one=True)
        if not row:
            return '📞 **لا يوجد بلاغات بعد.**'
        return (
            f'📞 **آخر بلاغ:**\n\n'
            f'**رقم:** {row["call_number"]}\n'
            f'**الموقع:** {row["location"]}\n'
            f'**الوصف:** {row["description"]}\n'
            f'**الحالة:** {row["status"]}'
        )

    # ─── أكثر ضابط نشاط ───
    if intent == 'top_officer':
        row = db_query(
            """SELECT user, COUNT(*) as c FROM activity_log
               GROUP BY user
               ORDER BY c DESC
               LIMIT 1""",
            one=True
        )
        if not row:
            return '🏆 مفيش بيانات نشاط بعد.'
        return f'🏆 **أكثر ضابط نشاطاً:** {row["user"]} — {row["c"]} نشاط'

    # ─── بحث مواطن ───
    if isinstance(intent, tuple) and intent[0] == 'search_citizen':
        name = intent[1]
        rows = db_query(
            "SELECT * FROM citizens WHERE full_name LIKE ? LIMIT 5",
            (f'%{name}%',)
        )
        if not rows:
            return f'🔍 مفيش نتائج للبحث عن: **{name}**'

        lines = [f'🔍 **نتائج البحث عن "{name}":**\n']
        for r in rows:
            status_emoji = {'CLEAN': '🟢', 'WARNING': '🟡', 'DANGEROUS': '🔴'}.get(r['status'], '⚪')
            lines.append(
                f'{status_emoji} **{r["full_name"]}**\n'
                f'   📞 {r["phone"] or "—"}\n'
                f'   🪪 {r["license_status"]}\n'
                f'   ⚠️ {r["status"]}'
            )
        return '\n\n'.join(lines)

    # ─── بحث مركبة ───
    if isinstance(intent, tuple) and intent[0] == 'search_vehicle':
        plate = intent[1]
        row = db_query(
            "SELECT * FROM vehicles WHERE plate LIKE ? LIMIT 1",
            (f'%{plate}%',), one=True
        )
        if not row:
            return f'🔍 مفيش مركبة برقم اللوحة: **{plate}**'

        return (
            f'🚗 **المركبة {row["plate"]}:**\n\n'
            f'**الموديل:** {row["model"] or "—"}\n'
            f'**اللون:** {row["color"] or "—"}\n'
            f'**المالك:** {row["owner_name"] or "—"}\n'
            f'**الحالة:** {row["status"]}\n'
            f'**التسجيل:** {row["registration_status"]}'
        )

    # ─── مش فاهم ───
    return (
        '🤔 **معلش، مفهمتش سؤالك.**\n\n'
        'جرب تسأل عن:\n'
        '• "كم عدد الضباط؟"\n'
        '• "القضايا المفتوحة"\n'
        '• "عدد البلاغات"\n'
        '• "مين في الشيفت؟"\n'
        '• "معلومات عن [اسم]"\n\n'
        'أو اكتب **"مساعدة"** عشان تشوف كل الأوامر.'
    )