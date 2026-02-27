import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import os
import io
from datetime import datetime, date, timedelta, time
from pathlib import Path

# ─────────────────────────────────────────────
# CONFIG & DB
# ─────────────────────────────────────────────
DB_PATH = Path(__file__).parent / "dochazka.db"

st.set_page_config(
    page_title="Docházkový systém",
    page_icon="🕐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# CUSTOM CSS  –  Exekutor Plus brand (light)
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@300;400;500;600;700&family=Source+Serif+4:wght@600;700&display=swap');

/* ── Tokens ────────────────────────────────── */
:root {
    --blue-dark:   #1a3a5c;
    --blue-mid:    #1a6aaa;
    --blue-bright: #2196c8;
    --blue-light:  #e8f3fb;
    --blue-xlight: #f0f7fd;
    --teal:        #2a9fd6;
    --white:       #ffffff;
    --bg:          #f4f7fa;
    --card-bg:     #ffffff;
    --border:      #dce6ef;
    --text-dark:   #1a2e4a;
    --text-body:   #3a5068;
    --text-muted:  #7a93ab;
    --green:       #1e8c5a;
    --green-bg:    #eaf7f1;
    --orange:      #c97b10;
    --orange-bg:   #fef6e8;
    --red:         #c0392b;
    --red-bg:      #fdf0ee;
    --radius:      10px;
    --shadow:      0 2px 8px rgba(26,58,92,.08);
    --shadow-md:   0 4px 16px rgba(26,58,92,.12);
}

html, body, [class*="css"] {
    font-family: 'Source Sans 3', 'Segoe UI', system-ui, sans-serif !important;
    color: var(--text-body);
}

/* ── App background ─────────────────────────── */
.stApp {
    background: var(--bg) !important;
}
.main .block-container {
    padding-top: 2rem;
    max-width: 1280px;
}

/* ── Sidebar ────────────────────────────────── */
[data-testid="stSidebar"] {
    background: var(--white) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * {
    color: var(--text-body) !important;
}
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    color: var(--text-body) !important;
    border: none !important;
    border-radius: 8px !important;
    text-align: left !important;
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    padding: 9px 14px !important;
    transition: all .15s !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: var(--blue-xlight) !important;
    color: var(--blue-mid) !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: var(--blue-mid) !important;
    color: var(--white) !important;
    font-weight: 600 !important;
}

/* ── Page header banner ─────────────────────── */
.page-header {
    background: linear-gradient(135deg, var(--blue-dark) 0%, var(--blue-bright) 100%);
    border-radius: var(--radius);
    padding: 28px 32px 26px;
    margin-bottom: 28px;
    position: relative;
    overflow: hidden;
}
.page-header::before {
    content: '';
    position: absolute;
    top: -40px; right: -40px;
    width: 200px; height: 200px;
    background: rgba(255,255,255,.05);
    border-radius: 50%;
}
.page-header h1 {
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 1.7rem;
    font-weight: 700;
    color: #ffffff !important;
    margin: 0 0 4px 0;
    line-height: 1.2;
}
.page-header p {
    font-size: 0.9rem;
    color: rgba(255,255,255,.75);
    margin: 0;
}

/* ── Stat cards ──────────────────────────────── */
.card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px 22px;
    margin-bottom: 14px;
    box-shadow: var(--shadow);
}
.card-green  { border-left: 4px solid #1e8c5a; }
.card-yellow { border-left: 4px solid #c97b10; }
.card-red    { border-left: 4px solid #c0392b; }
.card-blue   { border-left: 4px solid var(--blue-mid); }
.card-gray   { border-left: 4px solid #8fa8bf; }

.card h3 {
    margin: 0 0 6px 0;
    font-size: 0.72rem;
    color: var(--text-muted);
    font-weight: 600;
    letter-spacing: 0.07em;
    text-transform: uppercase;
}
.card .value {
    font-size: 1.9rem;
    font-weight: 700;
    color: var(--text-dark);
    font-variant-numeric: tabular-nums;
    line-height: 1.1;
}
.card .sub { font-size: 0.78rem; color: var(--text-muted); margin-top: 4px; }

/* ── Badges ─────────────────────────────────── */
.badge {
    display: inline-block;
    padding: 3px 11px;
    border-radius: 99px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.04em;
}
.badge-working  { background: #d4f5e5; color: #145c38; }
.badge-pause    { background: #fdefd4; color: #8b5500; }
.badge-sick     { background: #fde8e6; color: #9b2116; }
.badge-vacation { background: #d6eaf8;  color: #1a4f7a; }
.badge-offline  { background: #eaeef2; color: #5a7a8a; }

/* ── Person rows ────────────────────────────── */
.person-row {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 11px 16px;
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    margin-bottom: 7px;
    box-shadow: var(--shadow);
}
.avatar {
    width: 38px; height: 38px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 0.9rem;
    flex-shrink: 0;
    border: 2px solid rgba(255,255,255,.6);
}
.person-row .name   { font-weight: 600; font-size: 0.92rem; color: var(--text-dark); }
.person-row .detail { font-size: 0.77rem; color: var(--text-muted); }

/* ── Buttons ─────────────────────────────────── */
.stButton > button {
    background: var(--white);
    color: var(--blue-mid);
    border: 1.5px solid var(--border);
    border-radius: 8px;
    font-family: 'Source Sans 3', sans-serif;
    font-weight: 600;
    font-size: 0.88rem;
    transition: all .15s;
}
.stButton > button:hover {
    background: var(--blue-xlight);
    border-color: var(--blue-mid);
    color: var(--blue-dark);
}
.stButton > button[kind="primary"] {
    background: var(--blue-mid) !important;
    color: #ffffff !important;
    border-color: var(--blue-mid) !important;
}
.stButton > button[kind="primary"]:hover {
    background: var(--blue-dark) !important;
    border-color: var(--blue-dark) !important;
}

.btn-green  > button { border-color: var(--green)  !important; color: var(--green)  !important; background: var(--green-bg)  !important; }
.btn-red    > button { border-color: var(--red)    !important; color: var(--red)    !important; background: var(--red-bg)    !important; }
.btn-yellow > button { border-color: var(--orange) !important; color: var(--orange) !important; background: var(--orange-bg) !important; }
.btn-blue   > button { border-color: var(--blue-mid) !important; color: var(--white) !important; background: var(--blue-mid) !important; }

.btn-green  > button:hover { background: #c8f0e0 !important; }
.btn-red    > button:hover { background: #f8d8d4 !important; }
.btn-yellow > button:hover { background: #fde8c4 !important; }
.btn-blue   > button:hover { background: var(--blue-dark) !important; }

/* ── Divider ─────────────────────────────────── */
hr { border-color: var(--border) !important; }

/* ── Inputs / selects ───────────────────────── */
.stTextInput input,
.stSelectbox > div,
.stDateInput input {
    background: var(--white) !important;
    border: 1.5px solid var(--border) !important;
    border-radius: 8px !important;
    color: var(--text-dark) !important;
}
.stTextInput input:focus,
.stSelectbox > div:focus-within {
    border-color: var(--blue-mid) !important;
    box-shadow: 0 0 0 3px rgba(26,106,170,.12) !important;
}
label, .stSelectbox label, .stTextInput label, .stDateInput label {
    color: var(--text-body) !important;
    font-weight: 600 !important;
    font-size: 0.84rem !important;
}

/* ── Tabs ────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent;
    border-bottom: 2px solid var(--border);
    gap: 0;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    color: var(--text-muted);
    font-weight: 600;
    font-size: 0.87rem;
    border-bottom: 2px solid transparent;
    padding: 10px 18px;
    margin-bottom: -2px;
}
.stTabs [aria-selected="true"] {
    color: var(--blue-mid) !important;
    border-bottom: 2px solid var(--blue-mid) !important;
    background: transparent !important;
}

/* ── Dataframe ───────────────────────────────── */
.stDataFrame {
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    overflow: hidden;
}

/* ── Alerts ──────────────────────────────────── */
.stAlert {
    border-radius: var(--radius) !important;
}
.stSuccess { background: var(--green-bg) !important; color: var(--green) !important; border-color: #a8dfc6 !important; }
.stWarning { background: var(--orange-bg) !important; color: var(--orange) !important; }
.stError   { background: var(--red-bg) !important; color: var(--red) !important; }
.stInfo    { background: var(--blue-xlight) !important; color: var(--blue-dark) !important; }

/* ── Expander ─────────────────────────────────── */
.streamlit-expanderHeader {
    background: var(--white) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    color: var(--text-dark) !important;
    font-weight: 600 !important;
}

/* ── Sidebar brand block ─────────────────────── */
.sidebar-brand {
    background: linear-gradient(135deg, var(--blue-dark), var(--blue-bright));
    border-radius: var(--radius);
    padding: 18px 16px 16px;
    margin-bottom: 20px;
    text-align: center;
}
.sidebar-brand .brand-icon { font-size: 2rem; line-height: 1; }
.sidebar-brand .brand-title {
    font-family: 'Source Serif 4', serif;
    font-size: 0.85rem;
    font-weight: 700;
    color: rgba(255,255,255,.9);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-top: 6px;
}
.sidebar-brand .brand-sub {
    font-size: 0.72rem;
    color: rgba(255,255,255,.6);
    margin-top: 2px;
}
.sidebar-divider { height: 1px; background: var(--border); margin: 16px 0; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            color TEXT DEFAULT '#3b82f6',
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            checkin_time TEXT,
            checkout_time TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS pauses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attendance_id INTEGER NOT NULL,
            pause_type TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            FOREIGN KEY(attendance_id) REFERENCES attendance(id)
        );

        CREATE TABLE IF NOT EXISTS absences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            absence_type TEXT NOT NULL,
            date_from TEXT NOT NULL,
            date_to TEXT NOT NULL,
            note TEXT,
            approved INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """)
        # Seed admin if none exists
        row = conn.execute("SELECT id FROM users WHERE role='admin'").fetchone()
        if not row:
            conn.execute(
                "INSERT INTO users(username, password_hash, display_name, role, color) VALUES(?,?,?,?,?)",
                ("admin", hash_pw("admin123"), "Administrátor", "admin", "#ef4444")
            )
            conn.commit()

def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def authenticate(username: str, password: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username=? AND active=1", (username,)
        ).fetchone()
    if row and row["password_hash"] == hash_pw(password):
        return dict(row)
    return None

def get_all_users():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM users WHERE active=1 ORDER BY display_name").fetchall()]

def create_user(username, password, display_name, role, color):
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO users(username, password_hash, display_name, role, color) VALUES(?,?,?,?,?)",
                (username, hash_pw(password), display_name, role, color)
            )
            conn.commit()
        return True, "Uživatel vytvořen."
    except sqlite3.IntegrityError:
        return False, "Uživatelské jméno již existuje."

def update_user_password(user_id, new_password):
    with get_conn() as conn:
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_pw(new_password), user_id))
        conn.commit()

def deactivate_user(user_id):
    with get_conn() as conn:
        conn.execute("UPDATE users SET active=0 WHERE id=?", (user_id,))
        conn.commit()

# ── Attendance helpers ──

def today_str():
    return date.today().isoformat()

def now_str():
    return datetime.now().strftime("%H:%M:%S")

def get_attendance(user_id, day=None):
    if day is None:
        day = today_str()
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM attendance WHERE user_id=? AND date=?", (user_id, day)
        ).fetchone()

def ensure_attendance(user_id, day=None):
    if day is None:
        day = today_str()
    row = get_attendance(user_id, day)
    if row:
        return row["id"]
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO attendance(user_id, date) VALUES(?,?)", (user_id, day)
        )
        conn.commit()
        return cur.lastrowid

def do_checkin(user_id):
    att = get_attendance(user_id)
    if att and att["checkin_time"]:
        return False, "Příchod byl již zaznamenán."
    att_id = ensure_attendance(user_id)
    with get_conn() as conn:
        conn.execute("UPDATE attendance SET checkin_time=? WHERE id=?", (now_str(), att_id))
        conn.commit()
    return True, "Příchod zaznamenán ✓"

def do_checkout(user_id):
    att = get_attendance(user_id)
    if not att or not att["checkin_time"]:
        return False, "Nejprve zaznamenejte příchod."
    if att["checkout_time"]:
        return False, "Odchod byl již zaznamenán."
    # Close any open pauses
    close_open_pauses(att["id"])
    with get_conn() as conn:
        conn.execute("UPDATE attendance SET checkout_time=? WHERE id=?", (now_str(), att["id"]))
        conn.commit()
    return True, "Odchod zaznamenán ✓"

def get_pauses(att_id):
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM pauses WHERE attendance_id=? ORDER BY start_time", (att_id,)
        ).fetchall()]

def open_pause(att_id, pause_type):
    pauses = get_pauses(att_id)
    for p in pauses:
        if p["end_time"] is None:
            return False, "Existuje nezavřená pauza."
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO pauses(attendance_id, pause_type, start_time) VALUES(?,?,?)",
            (att_id, pause_type, now_str())
        )
        conn.commit()
    return True, f"Pauza ({pause_type}) zahájena."

def close_open_pauses(att_id):
    with get_conn() as conn:
        conn.execute(
            "UPDATE pauses SET end_time=? WHERE attendance_id=? AND end_time IS NULL",
            (now_str(), att_id)
        )
        conn.commit()

def end_pause(att_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM pauses WHERE attendance_id=? AND end_time IS NULL", (att_id,)
        ).fetchone()
        if not row:
            return False, "Žádná aktivní pauza."
        conn.execute("UPDATE pauses SET end_time=? WHERE id=?", (now_str(), row["id"]))
        conn.commit()
    return True, "Pauza ukončena ✓"

# ── Absences ──

def request_absence(user_id, absence_type, date_from, date_to, note=""):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO absences(user_id, absence_type, date_from, date_to, note) VALUES(?,?,?,?,?)",
            (user_id, absence_type, date_from.isoformat(), date_to.isoformat(), note)
        )
        conn.commit()

def get_absences_for_date(day=None):
    if day is None:
        day = today_str()
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            """SELECT a.*, u.display_name, u.color FROM absences a
               JOIN users u ON a.user_id=u.id
               WHERE a.date_from<=? AND a.date_to>=?""",
            (day, day)
        ).fetchall()]

def get_user_absences(user_id):
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM absences WHERE user_id=? ORDER BY date_from DESC", (user_id,)
        ).fetchall()]

def approve_absence(absence_id, approve: bool):
    with get_conn() as conn:
        conn.execute("UPDATE absences SET approved=? WHERE id=?", (1 if approve else -1, absence_id))
        conn.commit()

def delete_absence(absence_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM absences WHERE id=?", (absence_id,))
        conn.commit()

# ── Time calculations ──

def time_to_seconds(t_str: str) -> int:
    if not t_str:
        return 0
    parts = t_str.split(":")
    h, m, s = int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0
    return h * 3600 + m * 60 + s

def seconds_to_hm(seconds: int) -> str:
    seconds = max(0, seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}h {m:02d}m"

def calc_worked_seconds(att, pauses):
    if not att or not att["checkin_time"]:
        return 0
    checkout = att["checkout_time"] or now_str()
    total = time_to_seconds(checkout) - time_to_seconds(att["checkin_time"])
    for p in pauses:
        end = p["end_time"] or now_str()
        total -= (time_to_seconds(end) - time_to_seconds(p["start_time"]))
    return max(0, total)

def is_weekend(day_str: str) -> bool:
    d = date.fromisoformat(day_str)
    return d.weekday() >= 5

def get_month_stats(user_id, year: int, month: int):
    """Returns worked seconds per day, separating weekday vs weekend."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM attendance WHERE user_id=? AND strftime('%Y',date)=? AND strftime('%m',date)=?",
            (user_id, str(year), f"{month:02d}")
        ).fetchall()
    results = []
    for row in rows:
        att = dict(row)
        pauses = get_pauses(att["id"])
        worked = calc_worked_seconds(att, pauses) if att["checkin_time"] else 0
        results.append({
            "date": att["date"],
            "checkin": att["checkin_time"] or "",
            "checkout": att["checkout_time"] or "",
            "worked_seconds": worked,
            "is_weekend": is_weekend(att["date"]),
        })
    return results

def count_workdays_so_far(year: int, month: int) -> int:
    today = date.today()
    first = date(year, month, 1)
    # last day of month or today
    if year == today.year and month == today.month:
        last = today
    else:
        # last day of month
        if month == 12:
            last = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last = date(year, month + 1, 1) - timedelta(days=1)
    count = 0
    d = first
    while d <= last:
        if d.weekday() < 5:
            count += 1
        d += timedelta(days=1)
    return count

def get_status_overview():
    """Returns list of users with their today's status."""
    today = today_str()
    users = get_all_users()
    absences = get_absences_for_date(today)
    absent_ids = {a["user_id"]: a for a in absences}

    result = []
    for u in users:
        uid = u["id"]
        status = "offline"
        detail = ""
        checkin = None

        if uid in absent_ids:
            ab = absent_ids[uid]
            status = ab["absence_type"]
            detail = ab["note"] or ""
        else:
            att = get_attendance(uid, today)
            if att:
                if att["checkin_time"] and not att["checkout_time"]:
                    pauses = get_pauses(att["id"])
                    open_p = [p for p in pauses if p["end_time"] is None]
                    if open_p:
                        status = "pause"
                        detail = open_p[0]["pause_type"]
                    else:
                        status = "working"
                    checkin = att["checkin_time"][:5]
                elif att["checkout_time"]:
                    status = "done"
                    checkin = att["checkin_time"][:5] if att["checkin_time"] else ""
                    detail = f"odešel {att['checkout_time'][:5]}"

        result.append({**u, "status": status, "detail": detail, "checkin": checkin})
    return result

# ─────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────
AVATAR_COLORS = ["#3b82f6","#8b5cf6","#ec4899","#14b8a6","#f97316","#22c55e","#ef4444","#eab308"]

def avatar_html(name: str, color: str = "#1a6aaa") -> str:
    initials = "".join([w[0].upper() for w in name.split()[:2]])
    # lighter tint bg, solid color text
    return f'<div class="avatar" style="background:{color}22;color:{color};border:2px solid {color}44">{initials}</div>'

STATUS_LABEL = {
    "working": ("Pracuje", "working"),
    "pause": ("Pauza", "pause"),
    "sickday": ("Nemocný/á", "sick"),
    "vacation": ("Dovolená", "vacation"),
    "offline": ("Offline", "offline"),
    "done": ("Skončil/a", "offline"),
}

PAUSE_TYPES = ["🍽 Oběd", "🏥 Doktor", "☕ Přestávka", "📦 Jiné"]

# ─────────────────────────────────────────────
# PAGE: LOGIN
# ─────────────────────────────────────────────
def page_login():
    # Full-page gradient background for login
    st.markdown("""<style>
    .stApp { background: linear-gradient(135deg, #1a3a5c 0%, #2196c8 100%) !important; }
    .main .block-container { padding-top: 4rem; }
    </style>""", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("""
        <div style="background:#fff;border-radius:14px;padding:36px 36px 28px;
                    box-shadow:0 8px 40px rgba(26,58,92,.28);text-align:center;margin-bottom:0">
            <div style="font-size:2.4rem;margin-bottom:8px">🏛️</div>
            <div style="font-family:'Source Serif 4',Georgia,serif;font-size:1.1rem;
                        font-weight:700;color:#1a3a5c;letter-spacing:.04em;
                        text-transform:uppercase;margin-bottom:2px">
                Docházkový systém
            </div>
            <div style="font-size:0.78rem;color:#7a93ab;margin-bottom:24px">
                Exekutorský úřad Praha 4
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.container():
            st.markdown('<div style="background:#fff;border-radius:0 0 14px 14px;padding:0 36px 28px;box-shadow:0 8px 40px rgba(26,58,92,.28);">', unsafe_allow_html=True)
            with st.form("login_form"):
                username = st.text_input("Uživatelské jméno", placeholder="jmeno.prijmeni")
                password = st.text_input("Heslo", type="password", placeholder="••••••••")
                submitted = st.form_submit_button("Přihlásit se →", use_container_width=True, type="primary")
            st.markdown('</div>', unsafe_allow_html=True)

        if submitted:
            user = authenticate(username, password)
            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Nesprávné přihlašovací údaje.")

        st.markdown('<p style="text-align:center;color:rgba(255,255,255,.4);font-size:0.75rem;margin-top:20px">Výchozí admin: admin / admin123</p>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
# PAGE: DASHBOARD (today overview)
# ─────────────────────────────────────────────
def page_dashboard():
    st.markdown(f"""<div class="page-header">
        <h1>📊 Přehled dne</h1>
        <p>{date.today().strftime("%A, %d. %m. %Y")}</p>
    </div>""", unsafe_allow_html=True)

    overview = get_status_overview()

    working   = [u for u in overview if u["status"] == "working"]
    paused    = [u for u in overview if u["status"] == "pause"]
    sick      = [u for u in overview if u["status"] == "sickday"]
    vacation  = [u for u in overview if u["status"] == "vacation"]
    done      = [u for u in overview if u["status"] == "done"]
    offline   = [u for u in overview if u["status"] == "offline"]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class="card card-green">
            <h3>Pracují</h3><div class="value">{len(working)}</div>
            <div class="sub">{len(paused)} na pauze</div></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="card card-red">
            <h3>Nemocní</h3><div class="value">{len(sick)}</div>
            <div class="sub">sickday / nemoc</div></div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="card card-blue">
            <h3>Dovolená</h3><div class="value">{len(vacation)}</div>
            <div class="sub">volno</div></div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div class="card card-gray">
            <h3>Offline</h3><div class="value">{len(offline) + len(done)}</div>
            <div class="sub">{len(done)} skončilo</div></div>""", unsafe_allow_html=True)

    st.markdown("---")

    def render_group(title, users, show_checkin=False):
        if not users:
            return
        st.markdown(f'<div style="font-size:0.78rem;font-weight:700;color:#7a93ab;letter-spacing:.06em;text-transform:uppercase;margin:16px 0 8px">{title}</div>', unsafe_allow_html=True)
        for u in users:
            label, badge_cls = STATUS_LABEL.get(u["status"], ("", "offline"))
            detail_str = f" · {u['detail']}" if u["detail"] else ""
            checkin_str = f" · od {u['checkin']}" if show_checkin and u.get("checkin") else ""
            st.markdown(f"""
            <div class="person-row">
                {avatar_html(u['display_name'], u['color'])}
                <div style="flex:1">
                    <div class="name">{u['display_name']}</div>
                    <div class="detail">{detail_str.lstrip(' · ')}{checkin_str}</div>
                </div>
                <span class="badge badge-{badge_cls}">{label}</span>
            </div>""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

    col_l, col_r = st.columns(2)
    with col_l:
        render_group("🟢 Pracují", working, show_checkin=True)
        render_group("🟡 Na pauze", paused, show_checkin=True)
    with col_r:
        render_group("🔴 Sickday", sick)
        render_group("🔵 Dovolená", vacation)
        render_group("⚫ Skončili", done)

# ─────────────────────────────────────────────
# PAGE: MY ATTENDANCE (check-in/out)
# ─────────────────────────────────────────────
def page_my_attendance():
    user = st.session_state.user
    st.markdown(f"""<div class="page-header">
        <h1>🕐 Moje docházka</h1>
        <p>Dnes: {date.today().strftime("%d. %m. %Y")}</p>
    </div>""", unsafe_allow_html=True)

    # Check today's absence
    absences_today = get_absences_for_date()
    my_absence = next((a for a in absences_today if a["user_id"] == user["id"]), None)
    if my_absence:
        label = "Sickday" if my_absence["absence_type"] == "sickday" else "Dovolená"
        st.info(f"ℹ️ Dnes máš nahlášen/o: **{label}**. Docházka se nezaznamenává.")
        return

    att = get_attendance(user["id"])

    # ── Status card
    if att and att["checkin_time"]:
        pauses = get_pauses(att["id"])
        open_pauses = [p for p in pauses if p["end_time"] is None]
        worked = calc_worked_seconds(att, pauses)

        if open_pauses:
            op = open_pauses[0]
            st.markdown(f"""<div class="card card-yellow">
                <h3>Aktuální stav</h3>
                <div class="value" style="color:#8b5500">⏸ Pauza</div>
                <div class="sub">{op['pause_type']} od {op['start_time'][:5]} · odpracováno {seconds_to_hm(worked)}</div>
            </div>""", unsafe_allow_html=True)
        elif att["checkout_time"]:
            st.markdown(f"""<div class="card card-gray">
                <h3>Aktuální stav</h3>
                <div class="value" style="color:#5a7a8a">✅ Odhlášen/a</div>
                <div class="sub">Příchod {att['checkin_time'][:5]} · Odchod {att['checkout_time'][:5]} · Odpracováno {seconds_to_hm(worked)}</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""<div class="card card-green">
                <h3>Aktuální stav</h3>
                <div class="value" style="color:#145c38">▶ Pracuješ</div>
                <div class="sub">Příchod {att['checkin_time'][:5]} · Odpracováno {seconds_to_hm(worked)}</div>
            </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""<div class="card card-gray">
            <h3>Aktuální stav</h3>
            <div class="value" style="color:#5a7a8a">⭕ Offline</div>
            <div class="sub">Ještě jsi nezaznamenal/a příchod</div>
        </div>""", unsafe_allow_html=True)

    # ── Action buttons
    st.markdown("#### Akce")
    if not att or not att["checkin_time"]:
        col1, _ = st.columns([1, 3])
        with col1:
            st.markdown('<div class="btn-green">', unsafe_allow_html=True)
            if st.button("▶ Zaznamant příchod", use_container_width=True):
                ok, msg = do_checkin(user["id"])
                st.success(msg) if ok else st.warning(msg)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    elif att and att["checkin_time"] and not att["checkout_time"]:
        pauses = get_pauses(att["id"])
        open_pauses = [p for p in pauses if p["end_time"] is None]

        col1, col2 = st.columns([2, 2])
        with col1:
            if not open_pauses:
                st.markdown('<div class="btn-yellow">', unsafe_allow_html=True)
                pause_type = st.selectbox("Typ pauzy", PAUSE_TYPES, label_visibility="collapsed")
                if st.button("⏸ Zahájit pauzu", use_container_width=True):
                    ok, msg = open_pause(att["id"], pause_type)
                    st.success(msg) if ok else st.warning(msg)
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="btn-green">', unsafe_allow_html=True)
                if st.button("▶ Ukončit pauzu", use_container_width=True):
                    ok, msg = end_pause(att["id"])
                    st.success(msg) if ok else st.warning(msg)
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
        with col2:
            if not open_pauses:
                st.markdown('<div class="btn-red">', unsafe_allow_html=True)
                if st.button("⏹ Zaznamant odchod", use_container_width=True):
                    ok, msg = do_checkout(user["id"])
                    st.success(msg) if ok else st.warning(msg)
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    # ── Today's pauses history
    if att:
        pauses = get_pauses(att["id"])
        if pauses:
            st.markdown("#### Pauzy dnes")
            for p in pauses:
                end = p["end_time"][:5] if p["end_time"] else "probíhá…"
                duration = ""
                if p["end_time"]:
                    secs = time_to_seconds(p["end_time"]) - time_to_seconds(p["start_time"])
                    duration = f" ({seconds_to_hm(secs)})"
                st.markdown(f"- **{p['pause_type']}**: {p['start_time'][:5]} – {end}{duration}")

    # ── Monthly stats
    st.markdown("---")
    st.markdown("#### Statistiky měsíce")
    today = date.today()

    col_m, col_y = st.columns([1, 1])
    with col_m:
        month = st.selectbox("Měsíc", list(range(1, 13)),
                             index=today.month - 1,
                             format_func=lambda m: ["Leden","Únor","Březen","Duben","Květen","Červen",
                                                     "Červenec","Srpen","Září","Říjen","Listopad","Prosinec"][m-1])
    with col_y:
        year = st.selectbox("Rok", list(range(today.year - 1, today.year + 1)), index=1)

    stats = get_month_stats(user["id"], year, month)
    workdays_so_far = count_workdays_so_far(year, month)
    expected_seconds = workdays_so_far * 8 * 3600

    weekday_seconds = sum(s["worked_seconds"] for s in stats if not s["is_weekend"])
    weekend_seconds = sum(s["worked_seconds"] for s in stats if s["is_weekend"])
    total_seconds = weekday_seconds + weekend_seconds
    diff = weekday_seconds - expected_seconds

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class="card card-blue">
            <h3>Celkem odpracováno</h3>
            <div class="value" style="color:#1a3a5c">{seconds_to_hm(total_seconds)}</div>
            <div class="sub">vč. {seconds_to_hm(weekend_seconds)} víkend</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="card card-gray">
            <h3>Fond pracovní doby</h3>
            <div class="value" style="color:#3a5068">{seconds_to_hm(expected_seconds)}</div>
            <div class="sub">{workdays_so_far} pracovních dní</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        color = "green" if diff >= 0 else "red"
        val_color = "#145c38" if diff >= 0 else "#9b2116"
        sign = "+" if diff >= 0 else ""
        label = "Přesčas" if diff >= 0 else "Deficit"
        st.markdown(f"""<div class="card card-{color}">
            <h3>{label}</h3>
            <div class="value" style="color:{val_color}">{sign}{seconds_to_hm(abs(diff))}</div>
            <div class="sub">vs. fond {seconds_to_hm(expected_seconds)}</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        days_worked = len([s for s in stats if s["worked_seconds"] > 0 and not s["is_weekend"]])
        avg = (weekday_seconds // days_worked) if days_worked > 0 else 0
        c = "green" if avg >= 8 * 3600 else "yellow" if avg >= 6 * 3600 else "red"
        val_c = "#145c38" if avg >= 8*3600 else "#8b5500" if avg >= 6*3600 else "#9b2116"
        st.markdown(f"""<div class="card card-{c}">
            <h3>Průměr / den</h3>
            <div class="value" style="color:{val_c}">{seconds_to_hm(avg)}</div>
            <div class="sub">z {days_worked} odpracovaných dní</div>
        </div>""", unsafe_allow_html=True)

    if stats:
        df = pd.DataFrame(stats)
        df["worked"] = df["worked_seconds"].apply(seconds_to_hm)
        df["typ"] = df["is_weekend"].apply(lambda x: "🏖 Víkend" if x else "📋 Pracovní")
        df = df[["date", "checkin", "checkout", "worked", "typ"]].rename(columns={
            "date": "Datum", "checkin": "Příchod", "checkout": "Odchod",
            "worked": "Odpracováno", "typ": "Typ"
        })
        st.dataframe(df, use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────
# PAGE: ABSENCES
# ─────────────────────────────────────────────
def page_absences():
    user = st.session_state.user
    st.markdown("""<div class="page-header">
        <h1>🏖 Absence</h1>
        <p>Nahlášení sickday nebo dovolené</p>
    </div>""", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["➕ Nová žádost", "📋 Moje absence"])

    with tab1:
        abs_type = st.selectbox("Typ", ["sickday", "vacation"],
                                format_func=lambda x: "🤒 Sickday" if x == "sickday" else "🏖 Dovolená")

        if abs_type == "sickday":
            sick_date = st.date_input("Den nemoci", value=date.today(),
                                      min_value=date.today() - timedelta(days=30))
            date_from = sick_date
            date_to = sick_date
        else:
            col_od, col_do = st.columns(2)
            with col_od:
                date_from = st.date_input("Od", value=date.today(),
                                          min_value=date.today() - timedelta(days=30))
            with col_do:
                date_to = st.date_input("Do", value=date.today())

        note = st.text_input("Poznámka (nepovinné)")

        if st.button("Odeslat žádost", type="primary"):
            if date_to < date_from:
                st.error("Datum 'Do' musí být stejné nebo pozdější než 'Od'.")
            else:
                request_absence(user["id"], abs_type, date_from, date_to, note)
                st.success("Žádost byla odeslána ✓")
                st.rerun()

    with tab2:
        absences = get_user_absences(user["id"])
        if not absences:
            st.info("Žádné absence.")
        for a in absences:
            type_label = "🤒 Sickday" if a["absence_type"] == "sickday" else "🏖 Dovolená"
            status_map = {0: ("⏳ Čeká na schválení", "yellow"), 1: ("✅ Schváleno", "green"), -1: ("❌ Zamítnuto", "red")}
            status_str, s_color = status_map.get(a["approved"], ("?", "gray"))
            note_str = f" · {a['note']}" if a["note"] else ""
            date_str = a["date_from"] if a["date_from"] == a["date_to"] else f"{a['date_from']} – {a['date_to']}"
            st.markdown(f"""<div class="card card-{s_color}">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <div>
                        <strong style="color:#1a2e4a">{type_label}</strong>
                        <span style="color:#3a5068"> · {date_str}{note_str}</span><br>
                        <small style="color:#7a93ab">{status_str}</small>
                    </div>
                </div>
            </div>""", unsafe_allow_html=True)
            if a["approved"] == 0:
                if st.button(f"Zrušit žádost", key=f"del_abs_{a['id']}"):
                    delete_absence(a["id"])
                    st.rerun()

# ─────────────────────────────────────────────
# PAGE: ADMIN – REPORTS
# ─────────────────────────────────────────────
def page_reports():
    user = st.session_state.user
    is_admin = user["role"] == "admin"
    st.markdown("""<div class="page-header">
        <h1>📈 Výkazy docházky</h1>
        <p>Měsíční přehled odpracovaných hodin</p>
    </div>""", unsafe_allow_html=True)

    today = date.today()
    col1, col2, col3 = st.columns(3)
    with col1:
        month = st.selectbox("Měsíc", list(range(1, 13)), index=today.month - 1,
                             format_func=lambda m: ["Leden","Únor","Březen","Duben","Květen","Červen",
                                                     "Červenec","Srpen","Září","Říjen","Listopad","Prosinec"][m-1])
    with col2:
        year = st.selectbox("Rok", list(range(today.year - 1, today.year + 1)), index=1)
    with col3:
        if is_admin:
            users = get_all_users()
            user_options = {u["id"]: u["display_name"] for u in users}
            user_options[0] = "— Všichni zaměstnanci —"
            selected_uid = st.selectbox("Zaměstnanec", options=[0] + [u["id"] for u in users],
                                        format_func=lambda x: user_options[x])
        else:
            selected_uid = user["id"]
            st.text_input("Zaměstnanec", value=user["display_name"], disabled=True)

    if is_admin and selected_uid == 0:
        target_users = get_all_users()
    else:
        target_users = [next(u for u in get_all_users() if u["id"] == (selected_uid or user["id"]))]

    all_rows = []
    for tu in target_users:
        stats = get_month_stats(tu["id"], year, month)
        workdays = count_workdays_so_far(year, month)
        wd_sec = sum(s["worked_seconds"] for s in stats if not s["is_weekend"])
        we_sec = sum(s["worked_seconds"] for s in stats if s["is_weekend"])
        total_sec = wd_sec + we_sec
        expected = workdays * 8 * 3600
        diff = wd_sec - expected
        all_rows.append({
            "Jméno": tu["display_name"],
            "Pracovní dny": workdays,
            "Fond (h)": round(expected / 3600, 2),
            "Odpracováno (h)": round(wd_sec / 3600, 2),
            "Víkend (h)": round(we_sec / 3600, 2),
            "Celkem (h)": round(total_sec / 3600, 2),
            "Saldo (h)": round(diff / 3600, 2),
        })

    if all_rows:
        df = pd.DataFrame(all_rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # ── CSV export
        csv = df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")

        # ── XLSX export (summary sheet + per-user daily sheets)
        xlsx_buf = io.BytesIO()
        with pd.ExcelWriter(xlsx_buf, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Přehled", index=False)
            for tu in target_users:
                stats = get_month_stats(tu["id"], year, month)
                if stats:
                    df_day = pd.DataFrame(stats)
                    df_day["Odpracováno"] = df_day["worked_seconds"].apply(seconds_to_hm)
                    df_day["Typ dne"] = df_day["is_weekend"].apply(lambda x: "Víkend" if x else "Pracovní")
                    df_day = df_day[["date","checkin","checkout","Odpracováno","Typ dne"]].rename(columns={
                        "date": "Datum", "checkin": "Příchod", "checkout": "Odchod"
                    })
                    sheet_name = tu["display_name"][:31]  # Excel sheet name max 31 chars
                    df_day.to_excel(writer, sheet_name=sheet_name, index=False)
        xlsx_buf.seek(0)

        dl_col1, dl_col2, _ = st.columns([1, 1, 4])
        with dl_col1:
            st.download_button(
                "⬇ Stáhnout CSV",
                data=csv,
                file_name=f"dochazka_{year}_{month:02d}.csv",
                mime="text/csv",
            )
        with dl_col2:
            st.download_button(
                "⬇ Stáhnout XLSX",
                data=xlsx_buf,
                file_name=f"dochazka_{year}_{month:02d}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        if len(target_users) == 1 and (is_admin or selected_uid == user["id"]):
            st.markdown("---")
            st.markdown("#### Denní přehled")
            stats = get_month_stats(target_users[0]["id"], year, month)
            if stats:
                df2 = pd.DataFrame(stats)
                df2["worked"] = df2["worked_seconds"].apply(seconds_to_hm)
                df2["typ"] = df2["is_weekend"].apply(lambda x: "Víkend" if x else "Pracovní")
                df2 = df2[["date", "checkin", "checkout", "worked", "typ"]].rename(columns={
                    "date": "Datum", "checkin": "Příchod", "checkout": "Odchod",
                    "worked": "Odpracováno", "typ": "Typ dne"
                })
                st.dataframe(df2, use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────
# PAGE: ADMIN – MANAGE
# ─────────────────────────────────────────────
def page_admin():
    st.markdown("""<div class="page-header">
        <h1>⚙️ Správa uživatelů</h1>
        <p>Uživatelé, nemoci, schvalování absencí</p>
    </div>""", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["👥 Uživatelé", "➕ Nový uživatel", "🤒 Vložit nemoc", "✅ Schválení absencí"])

    with tab1:
        users = get_all_users()
        for u in users:
            with st.expander(f"{u['display_name']} (@{u['username']}) · {u['role']}"):
                col1, col2 = st.columns(2)
                with col1:
                    new_pw = st.text_input("Nové heslo", key=f"pw_{u['id']}", type="password")
                    if st.button("Změnit heslo", key=f"chpw_{u['id']}"):
                        if new_pw:
                            update_user_password(u["id"], new_pw)
                            st.success("Heslo změněno.")
                        else:
                            st.warning("Zadejte nové heslo.")
                with col2:
                    if u["id"] != st.session_state.user["id"]:
                        if st.button("⛔ Deaktivovat účet", key=f"del_{u['id']}"):
                            deactivate_user(u["id"])
                            st.warning(f"Účet {u['username']} byl deaktivován.")
                            st.rerun()

    with tab2:
        with st.form("new_user_form"):
            c1, c2 = st.columns(2)
            with c1:
                new_username = st.text_input("Uživatelské jméno")
                new_display = st.text_input("Celé jméno")
                new_color = st.color_picker("Barva avataru", value="#3b82f6")
            with c2:
                new_password = st.text_input("Heslo", type="password")
                new_role = st.selectbox("Role", ["user", "admin"])
            submitted = st.form_submit_button("Vytvořit uživatele", type="primary")
        if submitted:
            if new_username and new_password and new_display:
                ok, msg = create_user(new_username, new_password, new_display, new_role, new_color)
                st.success(msg) if ok else st.error(msg)
            else:
                st.warning("Vyplňte všechna povinná pole.")

    with tab3:
        st.markdown("Administrátor může přímo zaznamenat nemoc zaměstnance na libovolný den či rozsah dní. Absence bude automaticky schválena.")
        st.markdown("")
        users = get_all_users()
        user_options = {u["id"]: u["display_name"] for u in users}

        with st.form("admin_sick_form"):
            sick_uid = st.selectbox("Zaměstnanec", options=[u["id"] for u in users],
                                    format_func=lambda x: user_options[x])
            c1, c2 = st.columns(2)
            with c1:
                sick_from = st.date_input("Od (první den nemoci)", value=date.today())
            with c2:
                sick_to = st.date_input("Do (poslední den nemoci)", value=date.today())
            sick_note = st.text_input("Poznámka (nepovinné)", placeholder="např. neschopenka, karanténa…")
            submitted_sick = st.form_submit_button("🤒 Zaznamenat nemoc", type="primary")

        if submitted_sick:
            if sick_to < sick_from:
                st.error("Datum 'Do' musí být stejné nebo pozdější než 'Od'.")
            else:
                # Insert as approved (approved=1) directly
                with get_conn() as conn:
                    conn.execute(
                        "INSERT INTO absences(user_id, absence_type, date_from, date_to, note, approved) VALUES(?,?,?,?,?,1)",
                        (sick_uid, "sickday", sick_from.isoformat(), sick_to.isoformat(), sick_note)
                    )
                    conn.commit()
                emp_name = user_options[sick_uid]
                days = (sick_to - sick_from).days + 1
                st.success(f"Nemoc pro **{emp_name}** zaznamenána ({sick_from} – {sick_to}, {days} {'den' if days == 1 else 'dny' if days < 5 else 'dní'}) ✓")
                st.rerun()

        # Show recent admin-inserted sick days
        st.markdown("---")
        st.markdown("**Nedávno vložené nemoci**")
        with get_conn() as conn:
            recent = [dict(r) for r in conn.execute(
                """SELECT a.*, u.display_name FROM absences a
                   JOIN users u ON a.user_id=u.id
                   WHERE a.absence_type='sickday' AND a.approved=1
                   ORDER BY a.date_from DESC LIMIT 15"""
            ).fetchall()]
        if not recent:
            st.info("Žádné záznamy.")
        for r in recent:
            note_str = f" · {r['note']}" if r.get("note") else ""
            days = (date.fromisoformat(r["date_to"]) - date.fromisoformat(r["date_from"])).days + 1
            day_label = f"{r['date_from']}" if days == 1 else f"{r['date_from']} – {r['date_to']}"
            st.markdown(f"""<div class="card card-red" style="padding:14px 18px;margin-bottom:8px">
                <strong style="color:#1a2e4a">{r['display_name']}</strong>
                <span style="color:#c0392b"> · 🤒 Nemoc</span>
                <span style="color:#3a5068"> · {day_label}{note_str}</span>
            </div>""", unsafe_allow_html=True)
            if st.button("🗑 Smazat", key=f"del_sick_{r['id']}"):
                delete_absence(r["id"])
                st.rerun()

    with tab4:
        with get_conn() as conn:
            pending = [dict(r) for r in conn.execute(
                """SELECT a.*, u.display_name FROM absences a
                   JOIN users u ON a.user_id=u.id
                   WHERE a.approved=0 ORDER BY a.date_from"""
            ).fetchall()]

        if not pending:
            st.info("Žádné čekající žádosti.")
        for a in pending:
            type_label = "🤒 Sickday" if a["absence_type"] == "sickday" else "🏖 Dovolená"
            date_str = a['date_from'] if a['date_from'] == a['date_to'] else f"{a['date_from']} – {a['date_to']}"
            st.markdown(f"""<div class="card card-yellow">
                <strong style="color:#1a2e4a">{a['display_name']}</strong>
                <span style="color:#3a5068"> · {type_label} · {date_str}</span>
                <span style="color:#7a93ab">{(' · ' + a['note']) if a.get('note') else ''}</span>
            </div>""", unsafe_allow_html=True)
            col1, col2, _ = st.columns([1, 1, 4])
            with col1:
                if st.button("✅ Schválit", key=f"app_{a['id']}"):
                    approve_absence(a["id"], True)
                    st.rerun()
            with col2:
                if st.button("❌ Zamítnout", key=f"rej_{a['id']}"):
                    approve_absence(a["id"], False)
                    st.rerun()

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
init_db()

if "user" not in st.session_state:
    page_login()
else:
    user = st.session_state.user
    is_admin = user["role"] == "admin"

    with st.sidebar:
        st.markdown(f"""
        <div class="sidebar-brand">
            <div class="brand-icon">🏛️</div>
            <div class="brand-title">Docházkový systém</div>
            <div class="brand-sub">Exekutorský úřad Praha 4</div>
        </div>
        <div style="display:flex;align-items:center;gap:10px;padding:6px 4px 4px">
            {avatar_html(user['display_name'], user['color'])}
            <div>
                <div style="font-weight:700;font-size:0.9rem;color:#1a2e4a">{user['display_name']}</div>
                <div style="font-size:0.73rem;color:#7a93ab">{'Administrátor' if is_admin else 'Zaměstnanec'}</div>
            </div>
        </div>
        <div class="sidebar-divider"></div>
        """, unsafe_allow_html=True)

        pages = {
            "📊 Přehled dne": "dashboard",
            "🕐 Moje docházka": "attendance",
            "🏖 Absence": "absences",
            "📈 Výkazy": "reports",
        }
        if is_admin:
            pages["⚙️ Správa"] = "admin"

        if "page" not in st.session_state:
            st.session_state.page = "dashboard"

        for label, key in pages.items():
            if st.button(label, use_container_width=True,
                         type="primary" if st.session_state.page == key else "secondary"):
                st.session_state.page = key
                st.rerun()

        st.markdown("---")
        if st.button("🚪 Odhlásit se", use_container_width=True):
            del st.session_state.user
            st.session_state.page = "dashboard"
            st.rerun()

    page = st.session_state.page
    if page == "dashboard":
        page_dashboard()
    elif page == "attendance":
        page_my_attendance()
    elif page == "absences":
        page_absences()
    elif page == "reports":
        page_reports()
    elif page == "admin" and is_admin:
        page_admin()
