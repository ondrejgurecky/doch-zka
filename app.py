import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import os
import io
import base64
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date, timedelta, time
from pathlib import Path
from zoneinfo import ZoneInfo

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
DB_PATH   = Path(__file__).parent / "dochazka.db"
CET       = ZoneInfo("Europe/Prague")
BASE_DIR  = Path(__file__).parent

# ── E-mail (nastavte dle vašeho SMTP serveru) ─
SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587
SMTP_USER     = ""           # např. system@eupraha.cz
SMTP_PASSWORD = ""           # heslo nebo App Password
EMAIL_FROM    = "Docházkový systém <system@eupraha.cz>"
EMAIL_ENABLED = False        # True = skutečně odesílat; False = jen zobrazit simulaci

# ─────────────────────────────────────────────
# CET HELPERS
# ─────────────────────────────────────────────
def cet_now() -> datetime:
    return datetime.now(CET)

def cet_today() -> date:
    return cet_now().date()

def today_str() -> str:
    return cet_today().isoformat()

def now_str() -> str:
    return cet_now().strftime("%H:%M:%S")

# ─────────────────────────────────────────────
# LOGO HELPERS
# ─────────────────────────────────────────────
def _img_b64(path: Path) -> str:
    if path.exists():
        return base64.b64encode(path.read_bytes()).decode()
    return ""

def logo_img_tag(white: bool = False, height: int = 52) -> str:
    fname  = "logo_bile.png" if white else "logo_modre.png"
    b64    = _img_b64(BASE_DIR / fname)
    if b64:
        mime = "image/png"
        return f'<img src="data:{mime};base64,{b64}" style="height:{height}px;object-fit:contain;display:block">'
    # Fallback to hosted URL
    url = ("https://qtrypzzcjebvfcihiynt.supabase.co/storage/v1/object/public/"
           "base44-prod/public/699397941a2b8a2014ee9736/"
           + ("9e23cc13b_logo_bile_bezpozadi.png" if white else "98e058591_logo_modre_bezpozadi1.png"))
    return f'<img src="{url}" style="height:{height}px;object-fit:contain;display:block">'

def logo_st_path(white: bool = False) -> Path | None:
    fname = "logo_bile.png" if white else "logo_modre.png"
    p = BASE_DIR / fname
    return p if p.exists() else None

# ─────────────────────────────────────────────
# PAGE CONFIG & CSS
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Docházkový systém – Exekutorský úřad Praha 4",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ── Tokens – shodné s JSX ──────────────────── */
:root {
    --primary:   #1f5e8c;
    --primary-d: #0b5390;
    --bright:    #158bc8;
    --gradient:  linear-gradient(120deg, #0b5390 0%, #158bc8 81%);
    --white:     #ffffff;
    --bg:        #f8fafc;          /* slate-50 */
    --border:    #e2e8f0;          /* slate-200 */
    --text-dark: #1e293b;
    --text-body: #475569;
    --text-muted:#64748b;
    --radius-sm: 8px;
    --radius:    14px;
    --shadow:    0 1px 4px rgba(31,94,140,.07);
    --shadow-md: 0 4px 12px rgba(31,94,140,.10);
    /* semantic */
    --green:     #065f46;
    --green-bg:  #d1fae5;
    --red:       #991b1b;
    --red-bg:    #fee2e2;
    --orange:    #92400e;
    --orange-bg: #fef3c7;
    --blue-bg:   #e0f2fe;
}

/* ── Base ───────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
    -webkit-font-smoothing: antialiased !important;
    color: var(--text-body) !important;
}
.stApp { background: var(--bg) !important; }
.main .block-container { padding-top: 1.5rem; max-width: 1320px; }

/* ── Sidebar ────────────────────────────────── */
[data-testid="stSidebar"] {
    background: var(--white) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { color: var(--text-body) !important; }
[data-testid="stSidebar"] .stButton > button {
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
    width: 100% !important;
    background: transparent !important;
    color: var(--text-muted) !important;
    border: none !important;
    border-radius: 9px !important;
    text-align: left !important;
    font-size: .875rem !important;
    font-weight: 600 !important;
    padding: 10px 14px !important;
    margin-bottom: 2px !important;
    transition: all .15s !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: var(--bg) !important;
    color: var(--text-dark) !important;
}
/* Active nav item */
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: #e8f4fd !important;
    color: var(--primary) !important;
    font-weight: 700 !important;
}

/* ── Page section header (gradient banner) ─── */
.page-header {
    background: var(--gradient);
    border-radius: var(--radius);
    padding: 28px 36px;
    margin-bottom: 28px;
    position: relative;
    overflow: hidden;
}
.page-header::after {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 240px; height: 240px;
    background: rgba(255,255,255,.05);
    border-radius: 50%;
    pointer-events: none;
}
.page-header h1 {
    font-size: 1.625rem !important;
    font-weight: 800 !important;
    color: #fff !important;
    margin: 0 0 4px !important;
    line-height: 1.2 !important;
    letter-spacing: -.3px !important;
}
.page-header p { font-size: .875rem; color: rgba(255,255,255,.75); margin: 0; }

/* ── Cards ─────────────────────────────────── */
.card {
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px 24px;
    margin-bottom: 14px;
    box-shadow: var(--shadow);
}
/* Coloured left accent – kept for stat cards */
.card-green  { border-left: 4px solid #059669; }
.card-yellow { border-left: 4px solid #d97706; }
.card-red    { border-left: 4px solid #dc2626; }
.card-blue   { border-left: 4px solid var(--primary); }
.card-gray   { border-left: 4px solid #94a3b8; }

.card h3 {
    margin: 0 0 6px;
    font-size: .7rem;
    color: var(--text-muted);
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
}
.card .value {
    font-size: 1.875rem;
    font-weight: 800;
    color: var(--text-dark);
    font-variant-numeric: tabular-nums;
    line-height: 1.1;
}
.card .sub { font-size: .75rem; color: var(--text-muted); margin-top: 4px; }

/* ── Status / request badges ─────────────────  */
.badge {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 6px;
    font-size: .7rem;
    font-weight: 700;
    letter-spacing: .03em;
}
.badge-working  { background: var(--green-bg);  color: var(--green); }
.badge-pause    { background: var(--orange-bg); color: var(--orange); }
.badge-sick     { background: var(--red-bg);    color: var(--red); }
.badge-vacation { background: var(--blue-bg);   color: var(--primary); }
.badge-offline  { background: #f1f5f9;          color: #475569; }
.badge-pending  { background: var(--orange-bg); color: var(--orange); }
.badge-approved { background: var(--green-bg);  color: var(--green); }
.badge-rejected { background: var(--red-bg);    color: var(--red); }

/* ── Person rows ────────────────────────────── */
.person-row {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 12px 18px;
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    margin-bottom: 8px;
    box-shadow: var(--shadow);
}
.avatar {
    width: 40px; height: 40px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: .95rem; flex-shrink: 0;
}
.person-row .name   { font-weight: 700; font-size: .9rem;  color: var(--text-dark); }
.person-row .detail { font-size: .76rem; color: var(--text-muted); }

/* ── Buttons (global) ───────────────────────── */
.stButton > button {
    background: var(--white) !important;
    color: var(--primary) !important;
    border: 1.5px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: .875rem !important;
    transition: all .15s !important;
}
.stButton > button:hover {
    background: var(--bg) !important;
    border-color: var(--primary) !important;
}
/* primary = gradient */
.stButton > button[kind="primary"] {
    background: var(--gradient) !important;
    color: #fff !important;
    border: none !important;
}
.stButton > button[kind="primary"]:hover {
    opacity: .9 !important;
}
/* coloured helper wrappers */
.btn-green  > button { background: var(--green-bg)  !important; color: var(--green)  !important; border-color: #6ee7b7 !important; }
.btn-red    > button { background: var(--red-bg)    !important; color: var(--red)    !important; border-color: #fca5a5 !important; }
.btn-yellow > button { background: var(--orange-bg) !important; color: var(--orange) !important; border-color: #fcd34d !important; }
.btn-green  > button:hover { background: #a7f3d0 !important; }
.btn-red    > button:hover { background: #fecaca !important; }
.btn-yellow > button:hover { background: #fde68a !important; }

/* ── Form inputs ────────────────────────────── */
.stTextInput input,
.stSelectbox > div,
.stDateInput input,
.stTextArea textarea {
    background: var(--white) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-dark) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: .875rem !important;
}
.stTextInput input:focus,
.stSelectbox > div:focus-within,
.stTextArea textarea:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px rgba(31,94,140,.1) !important;
}
label,
.stSelectbox label, .stTextInput label,
.stDateInput label, .stTextArea label {
    color: var(--text-body) !important;
    font-weight: 600 !important;
    font-size: .8125rem !important;
}

/* ── Tabs ───────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid var(--border) !important;
    gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--text-muted) !important;
    font-weight: 600 !important;
    font-size: .875rem !important;
    border-bottom: 2px solid transparent !important;
    padding: 10px 18px !important;
    margin-bottom: -1px !important;
}
.stTabs [aria-selected="true"] {
    color: var(--primary) !important;
    border-bottom: 2px solid var(--primary) !important;
    background: transparent !important;
}

/* ── Dataframe ──────────────────────────────── */
.stDataFrame {
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    overflow: hidden !important;
    box-shadow: var(--shadow) !important;
}

/* ── Alerts ─────────────────────────────────── */
.stSuccess { background: var(--green-bg) !important; color: var(--green) !important; border-radius: var(--radius-sm) !important; }
.stInfo    { background: var(--blue-bg)  !important; color: var(--primary) !important; border-radius: var(--radius-sm) !important; }
.stWarning { background: var(--orange-bg)!important; color: var(--orange) !important; border-radius: var(--radius-sm) !important; }
.stError   { background: var(--red-bg)   !important; color: var(--red)    !important; border-radius: var(--radius-sm) !important; }

/* ── Expander ───────────────────────────────── */
.streamlit-expanderHeader {
    background: var(--white) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-dark) !important;
    font-weight: 700 !important;
    font-size: .875rem !important;
}

/* ── Misc ───────────────────────────────────── */
hr { border-color: var(--border) !important; }
.sidebar-divider { height: 1px; background: var(--border); margin: 12px 0; }

/* Stat number pull-out (JSX style) */
.stat-val {
    font-size: 2rem;
    font-weight: 800;
    color: var(--primary);
    font-variant-numeric: tabular-nums;
    letter-spacing: -1px;
    line-height: 1;
}
.stat-label {
    font-size: .6875rem;
    font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: .06em;
    margin-bottom: 4px;
}
.stat-sub { font-size: .75rem; color: var(--text-muted); margin-top: 6px; }

/* Clock widget inner block */
.clock-block {
    background: #f0f7ff;
    border-radius: 10px;
    padding: 12px 20px;
    display: inline-block;
    text-align: center;
}
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
            color TEXT DEFAULT '#1f5e8c',
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
            email_sent INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS time_corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            orig_in TEXT,
            orig_out TEXT,
            orig_break_start TEXT,
            orig_break_end TEXT,
            req_in TEXT NOT NULL,
            req_out TEXT NOT NULL,
            req_break_start TEXT,
            req_break_end TEXT,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            admin_note TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """)
        # email_sent column migration for existing DBs
        try:
            conn.execute("ALTER TABLE absences ADD COLUMN email_sent INTEGER DEFAULT 0")
            conn.commit()
        except Exception:
            pass
        # Seed admin
        row = conn.execute("SELECT id FROM users WHERE role='admin'").fetchone()
        if not row:
            conn.execute(
                "INSERT INTO users(username,password_hash,display_name,role,color) VALUES(?,?,?,?,?)",
                ("admin", hash_pw("admin123"), "Administrátor", "admin", "#1f5e8c")
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
        return [dict(r) for r in conn.execute(
            "SELECT * FROM users WHERE active=1 ORDER BY display_name"
        ).fetchall()]

def create_user(username, password, display_name, role, color):
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO users(username,password_hash,display_name,role,color) VALUES(?,?,?,?,?)",
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

def update_user_name(user_id, new_name: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET display_name=? WHERE id=?", (new_name.strip(), user_id))
        conn.commit()

def deactivate_user(user_id):
    with get_conn() as conn:
        conn.execute("UPDATE users SET active=0 WHERE id=?", (user_id,))
        conn.commit()

# ── Attendance ──
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
            "INSERT INTO attendance(user_id,date) VALUES(?,?)", (user_id, day)
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
            "INSERT INTO pauses(attendance_id,pause_type,start_time) VALUES(?,?,?)",
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
            "INSERT INTO absences(user_id,absence_type,date_from,date_to,note) VALUES(?,?,?,?,?)",
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

def approve_absence(absence_id: int, approve: bool, user_email: str = "", user_name: str = ""):
    val = 1 if approve else -1
    with get_conn() as conn:
        conn.execute("UPDATE absences SET approved=? WHERE id=?", (val, absence_id))
        conn.commit()
        ab = dict(conn.execute("SELECT * FROM absences WHERE id=?", (absence_id,)).fetchone())

    email_sent = False
    if approve and user_email:
        email_sent = send_absence_email(user_email, user_name, ab)
        if email_sent:
            with get_conn() as conn:
                conn.execute("UPDATE absences SET email_sent=1 WHERE id=?", (absence_id,))
                conn.commit()
    return email_sent

def delete_absence(absence_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM absences WHERE id=?", (absence_id,))
        conn.commit()

# ── Time corrections ──
def request_correction(user_id, d, orig_in, orig_out, orig_bs, orig_be,
                        req_in, req_out, req_bs, req_be, reason):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO time_corrections
               (user_id,date,orig_in,orig_out,orig_break_start,orig_break_end,
                req_in,req_out,req_break_start,req_break_end,reason,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (user_id, d, orig_in, orig_out, orig_bs, orig_be,
             req_in, req_out, req_bs, req_be, reason, cet_now().isoformat())
        )
        conn.commit()

def get_user_corrections(user_id):
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM time_corrections WHERE user_id=? ORDER BY created_at DESC", (user_id,)
        ).fetchall()]

def get_pending_corrections():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            """SELECT tc.*, u.display_name, u.email FROM time_corrections tc
               JOIN users u ON tc.user_id=u.id
               WHERE tc.status='pending' ORDER BY tc.created_at""",
        ).fetchall()]

def resolve_correction(correction_id: int, approve: bool, admin_note: str = ""):
    status = "approved" if approve else "rejected"
    with get_conn() as conn:
        conn.execute(
            "UPDATE time_corrections SET status=?, admin_note=? WHERE id=?",
            (status, admin_note, correction_id)
        )
        conn.commit()

# ── E-mail ──
def send_absence_email(to_email: str, to_name: str, absence: dict) -> bool:
    type_cz = "Dovolená" if absence["absence_type"] == "vacation" else "Sickday / Nemoc"
    date_str = absence["date_from"] if absence["date_from"] == absence["date_to"] \
               else f"{absence['date_from']} – {absence['date_to']}"
    note_str = f"\nPoznámka: {absence['note']}" if absence.get("note") else ""

    subject = f"[Docházkový systém] Vaše žádost o absenci byla schválena"
    body = (f"Dobrý den, {to_name},\n\n"
            f"Vaše žádost o absenci byla schválena.\n\n"
            f"Typ:    {type_cz}\n"
            f"Datum:  {date_str}{note_str}\n\n"
            f"S pozdravem,\n"
            f"Docházkový systém – Exekutorský úřad Praha 4\n"
            f"urad@eupraha.cz | +420 241 434 045")

    if not EMAIL_ENABLED:
        # Simulace – uložíme do session_state pro zobrazení
        st.session_state.setdefault("email_log", []).append({
            "to": to_email, "subject": subject, "body": body
        })
        return True  # považujeme za "odesláno" (simulace)

    try:
        msg = MIMEMultipart()
        msg["From"]    = EMAIL_FROM
        msg["To"]      = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.sendmail(EMAIL_FROM, to_email, msg.as_string())
        return True
    except Exception as e:
        st.warning(f"Email se nepodařilo odeslat: {e}")
        return False

# ── Time helpers ──
def time_to_seconds(t_str: str) -> int:
    if not t_str:
        return 0
    parts = t_str.split(":")
    h, m, s = int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0
    return h * 3600 + m * 60 + s

def seconds_to_hm(seconds: int) -> str:
    seconds = max(0, seconds)
    return f"{seconds // 3600}h {(seconds % 3600) // 60:02d}m"

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
    return date.fromisoformat(day_str).weekday() >= 5

def get_month_stats(user_id, year: int, month: int):
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
            "date": att["date"], "checkin": att["checkin_time"] or "",
            "checkout": att["checkout_time"] or "",
            "worked_seconds": worked, "is_weekend": is_weekend(att["date"]),
        })
    return results

def count_workdays_so_far(year: int, month: int) -> int:
    today = cet_today()
    first = date(year, month, 1)
    if year == today.year and month == today.month:
        last = today
    else:
        last = (date(year, month + 1, 1) - timedelta(days=1)) if month < 12 else date(year, 12, 31)
    count, d = 0, first
    while d <= last:
        if d.weekday() < 5:
            count += 1
        d += timedelta(days=1)
    return count

def get_status_overview():
    today = today_str()
    users = get_all_users()
    absences = get_absences_for_date(today)
    absent_ids = {a["user_id"]: a for a in absences}
    result = []
    for u in users:
        uid = u["id"]
        status, detail, checkin = "offline", "", None
        if uid in absent_ids:
            ab = absent_ids[uid]
            status = ab["absence_type"]
            detail = ab["note"] or ""
        else:
            att = get_attendance(uid, today)
            if att:
                if att["checkin_time"] and not att["checkout_time"]:
                    open_p = [p for p in get_pauses(att["id"]) if p["end_time"] is None]
                    status  = "pause" if open_p else "working"
                    detail  = open_p[0]["pause_type"] if open_p else ""
                    checkin = att["checkin_time"][:5]
                elif att["checkout_time"]:
                    status  = "done"
                    checkin = att["checkin_time"][:5] if att["checkin_time"] else ""
                    detail  = f"odešel {att['checkout_time'][:5]}"
        result.append({**u, "status": status, "detail": detail, "checkin": checkin})
    return result

# ─────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────
def avatar_html(name: str, color: str = "#1f5e8c") -> str:
    initials = "".join([w[0].upper() for w in name.split()[:2]])
    return f'<div class="avatar" style="background:{color}22;color:{color};border:2px solid {color}55">{initials}</div>'

STATUS_LABEL = {
    "working": ("Pracuje",   "working"),
    "pause":   ("Pauza",     "pause"),
    "sickday": ("Nemocný/á", "sick"),
    "vacation":("Dovolená",  "vacation"),
    "offline": ("Offline",   "offline"),
    "done":    ("Skončil/a", "offline"),
}
PAUSE_TYPES = ["🍽 Oběd", "🏥 Doktor", "☕ Přestávka", "📦 Jiné"]
MONTH_NAMES = ["Leden","Únor","Březen","Duben","Květen","Červen",
               "Červenec","Srpen","Září","Říjen","Listopad","Prosinec"]

def status_badge(status: str) -> str:
    label, cls = STATUS_LABEL.get(status, ("", "offline"))
    return f'<span class="badge badge-{cls}">{label}</span>'

def correction_status_badge(status: str) -> str:
    labels = {"pending": ("⏳ Čeká", "pending"), "approved": ("✅ Schváleno", "approved"), "rejected": ("❌ Zamítnuto", "rejected")}
    label, cls = labels.get(status, ("?", "offline"))
    return f'<span class="badge badge-{cls}">{label}</span>'


# ─────────────────────────────────────────────
# PAGE: LOGIN
# ─────────────────────────────────────────────
def page_login():
    st.markdown("""<style>
    .stApp { background: linear-gradient(120deg,#0b5390 0%,#158bc8 81%) !important; }
    .main .block-container { padding-top: 5rem; }
    </style>""", unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.1, 1])
    with col:
        # Card top – logo + title
        st.markdown(f"""
        <div style="background:#fff;border-radius:14px 14px 0 0;
                    padding:36px 40px 24px;
                    box-shadow:0 8px 40px rgba(11,83,144,.3);
                    text-align:center">
            <div style="display:flex;justify-content:center;margin-bottom:20px">
                {logo_img_tag(white=False, height=56)}
            </div>
            <div style="font-size:1.1rem;font-weight:800;color:#1e293b;
                        letter-spacing:-.3px;margin-bottom:4px">
                Docházkový systém
            </div>
            <div style="font-size:.8rem;color:#64748b">
                Exekutorský úřad Praha 4 – Mgr. Jan Škarpa
            </div>
        </div>""", unsafe_allow_html=True)

        # Card bottom – form
        st.markdown("""
        <div style="background:#fff;border-radius:0 0 14px 14px;
                    padding:4px 40px 32px;
                    box-shadow:0 8px 40px rgba(11,83,144,.3);">
        """, unsafe_allow_html=True)
        with st.form("login_form"):
            username  = st.text_input("Uživatelské jméno", placeholder="jmeno.prijmeni")
            password  = st.text_input("Heslo", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Přihlásit se →",
                                              use_container_width=True, type="primary")
        st.markdown('</div>', unsafe_allow_html=True)

        if submitted:
            user = authenticate(username, password)
            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Nesprávné přihlašovací údaje.")

        st.markdown("""
        <p style="text-align:center;color:rgba(255,255,255,.45);
                  font-size:.75rem;margin-top:18px">
            Výchozí admin: admin / admin123
        </p>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# PAGE: DASHBOARD
# ─────────────────────────────────────────────
def page_dashboard():
    today_cet = cet_today()
    st.markdown(f"""<div class="page-header">
        <h1>📊 Přehled dne</h1>
        <p>{today_cet.strftime("%-d. %-m. %Y")} · čas CET: {cet_now().strftime("%H:%M")}</p>
    </div>""", unsafe_allow_html=True)

    overview = get_status_overview()
    working  = [u for u in overview if u["status"] == "working"]
    paused   = [u for u in overview if u["status"] == "pause"]
    sick     = [u for u in overview if u["status"] == "sickday"]
    vacation = [u for u in overview if u["status"] == "vacation"]
    done     = [u for u in overview if u["status"] == "done"]
    offline  = [u for u in overview if u["status"] == "offline"]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class="card card-green"><h3>Pracují</h3>
            <div class="value">{len(working)}</div>
            <div class="sub">{len(paused)} na pauze</div></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="card card-red"><h3>Nemocní</h3>
            <div class="value">{len(sick)}</div><div class="sub">sickday / PN</div></div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="card card-blue"><h3>Dovolená</h3>
            <div class="value">{len(vacation)}</div><div class="sub">schválené volno</div></div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div class="card card-gray"><h3>Offline / Odešli</h3>
            <div class="value">{len(offline) + len(done)}</div>
            <div class="sub">{len(done)} skončilo dnes</div></div>""", unsafe_allow_html=True)

    st.markdown("---")

    def render_group(title, users, show_checkin=False):
        if not users:
            return
        st.markdown(f'<div style="font-size:.75rem;font-weight:700;color:#7a93ab;letter-spacing:.06em;text-transform:uppercase;margin:14px 0 8px">{title}</div>', unsafe_allow_html=True)
        for u in users:
            detail_str  = u["detail"] or ""
            checkin_str = f" · od {u['checkin']}" if show_checkin and u.get("checkin") else ""
            st.markdown(f"""
            <div class="person-row">
                {avatar_html(u['display_name'], u['color'])}
                <div style="flex:1">
                    <div class="name">{u['display_name']}</div>
                    <div class="detail">{detail_str}{checkin_str}</div>
                </div>
                {status_badge(u['status'])}
            </div>""", unsafe_allow_html=True)

    col_l, col_r = st.columns(2)
    with col_l:
        render_group("🟢 Pracují", working, show_checkin=True)
        render_group("🟡 Na pauze", paused, show_checkin=True)
    with col_r:
        render_group("🔴 Sickday / Nemoc", sick)
        render_group("🔵 Dovolená", vacation)
        render_group("⚫ Skončili / Offline", done + offline)


# ─────────────────────────────────────────────
# PAGE: MY ATTENDANCE
# ─────────────────────────────────────────────
def page_my_attendance():
    user = st.session_state.user
    today_cet = cet_today()
    st.markdown(f"""<div class="page-header">
        <h1>🕐 Moje docházka</h1>
        <p>Dnes: {today_cet.strftime("%-d. %-m. %Y")} · {cet_now().strftime("%H:%M")} CET</p>
    </div>""", unsafe_allow_html=True)

    absences_today = get_absences_for_date()
    my_absence = next((a for a in absences_today if a["user_id"] == user["id"]), None)
    if my_absence:
        label = "Dovolená" if my_absence["absence_type"] == "vacation" else "Sickday / Nemoc"
        st.info(f"ℹ️ Dnes máš nahlášen/o: **{label}**. Docházka se nezaznamenává.")
        return

    att = get_attendance(user["id"])

    # Status card
    if att and att["checkin_time"]:
        pauses = get_pauses(att["id"])
        open_p = [p for p in pauses if p["end_time"] is None]
        worked = calc_worked_seconds(att, pauses)
        if open_p:
            st.markdown(f"""<div class="card card-yellow">
                <h3>Aktuální stav</h3>
                <div class="value" style="color:#8b5500">⏸ Pauza</div>
                <div class="sub">{open_p[0]['pause_type']} od {open_p[0]['start_time'][:5]} · odpracováno {seconds_to_hm(worked)}</div>
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

    # Action buttons
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
    elif att["checkin_time"] and not att["checkout_time"]:
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

    if att:
        pauses = get_pauses(att["id"])
        if pauses:
            st.markdown("#### Pauzy dnes")
            for p in pauses:
                end = p["end_time"][:5] if p["end_time"] else "probíhá…"
                dur = ""
                if p["end_time"]:
                    secs = time_to_seconds(p["end_time"]) - time_to_seconds(p["start_time"])
                    dur = f" ({seconds_to_hm(secs)})"
                st.markdown(f"- **{p['pause_type']}**: {p['start_time'][:5]} – {end}{dur}")

    # Monthly stats
    st.markdown("---")
    st.markdown("#### Statistiky měsíce")
    today = cet_today()
    col_m, col_y = st.columns([1, 1])
    with col_m:
        month = st.selectbox("Měsíc", list(range(1, 13)), index=today.month - 1,
                             format_func=lambda m: MONTH_NAMES[m-1])
    with col_y:
        year = st.selectbox("Rok", list(range(today.year - 1, today.year + 1)), index=1)

    stats = get_month_stats(user["id"], year, month)
    workdays_so_far = count_workdays_so_far(year, month)
    expected_sec    = workdays_so_far * 8 * 3600
    wd_sec  = sum(s["worked_seconds"] for s in stats if not s["is_weekend"])
    we_sec  = sum(s["worked_seconds"] for s in stats if s["is_weekend"])
    diff    = wd_sec - expected_sec

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class="card card-blue"><h3>Celkem odpracováno</h3>
            <div class="value" style="color:#1a3a5c">{seconds_to_hm(wd_sec + we_sec)}</div>
            <div class="sub">vč. {seconds_to_hm(we_sec)} víkend</div></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="card card-gray"><h3>Fond pracovní doby</h3>
            <div class="value" style="color:#3a5068">{seconds_to_hm(expected_sec)}</div>
            <div class="sub">{workdays_so_far} pracovních dní</div></div>""", unsafe_allow_html=True)
    with c3:
        color    = "green" if diff >= 0 else "red"
        val_col  = "#145c38" if diff >= 0 else "#9b2116"
        sign     = "+" if diff >= 0 else ""
        label    = "Přesčas" if diff >= 0 else "Deficit"
        st.markdown(f"""<div class="card card-{color}"><h3>{label}</h3>
            <div class="value" style="color:{val_col}">{sign}{seconds_to_hm(abs(diff))}</div></div>""", unsafe_allow_html=True)
    with c4:
        days_worked = len([s for s in stats if s["worked_seconds"] > 0 and not s["is_weekend"]])
        avg = (wd_sec // days_worked) if days_worked > 0 else 0
        c  = "green" if avg >= 8*3600 else "yellow" if avg >= 6*3600 else "red"
        vc = "#145c38" if avg >= 8*3600 else "#8b5500" if avg >= 6*3600 else "#9b2116"
        st.markdown(f"""<div class="card card-{c}"><h3>Průměr / den</h3>
            <div class="value" style="color:{vc}">{seconds_to_hm(avg)}</div>
            <div class="sub">z {days_worked} dní</div></div>""", unsafe_allow_html=True)

    if stats:
        df = pd.DataFrame(stats)
        df["Odpracováno"] = df["worked_seconds"].apply(seconds_to_hm)
        df["Typ"]         = df["is_weekend"].apply(lambda x: "🏖 Víkend" if x else "📋 Pracovní")
        df = df[["date","checkin","checkout","Odpracováno","Typ"]].rename(
            columns={"date":"Datum","checkin":"Příchod","checkout":"Odchod"})
        st.dataframe(df, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────
# PAGE: ABSENCES
# ─────────────────────────────────────────────
def page_absences():
    user = st.session_state.user
    st.markdown("""<div class="page-header">
        <h1>🏖 Absence</h1>
        <p>Nahlášení dovolené nebo sickday – čeká na schválení administrátora</p>
    </div>""", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["➕ Nová žádost", "📋 Moje absence"])

    with tab1:
        abs_type = st.selectbox("Typ", ["sickday", "vacation"],
                                format_func=lambda x: "🤒 Sickday / Nemoc" if x == "sickday" else "🏖 Dovolená")
        if abs_type == "sickday":
            sick_date = st.date_input("Den nemoci", value=cet_today(),
                                      min_value=cet_today() - timedelta(days=30))
            date_from = date_to = sick_date
        else:
            c1, c2 = st.columns(2)
            with c1:
                date_from = st.date_input("Od", value=cet_today())
            with c2:
                date_to   = st.date_input("Do", value=cet_today())
        note = st.text_input("Poznámka (nepovinné)")
        if st.button("Odeslat žádost", type="primary"):
            if date_to < date_from:
                st.error("Datum 'Do' musí být stejné nebo pozdější než 'Od'.")
            else:
                request_absence(user["id"], abs_type, date_from, date_to, note)
                st.success("Žádost odeslána – čeká na schválení administrátorem ✓")
                st.rerun()

    with tab2:
        absences = get_user_absences(user["id"])
        if not absences:
            st.info("Žádné absence.")
        type_labels = {"sickday": "🤒 Sickday", "vacation": "🏖 Dovolená"}
        status_map  = {0: ("⏳ Čeká na schválení", "yellow"), 1: ("✅ Schváleno", "green"), -1: ("❌ Zamítnuto", "red")}
        for a in absences:
            type_label = type_labels.get(a["absence_type"], a["absence_type"])
            status_str, s_color = status_map.get(a["approved"], ("?", "gray"))
            note_str = f" · {a['note']}" if a.get("note") else ""
            date_str = a["date_from"] if a["date_from"] == a["date_to"] else f"{a['date_from']} – {a['date_to']}"
            email_str = " · ✉ Potvrzení zasláno emailem" if a.get("email_sent") else ""
            st.markdown(f"""<div class="card card-{s_color}">
                <strong style="color:#1a2e4a">{type_label}</strong>
                <span style="color:#3a5068"> · {date_str}{note_str}</span><br>
                <small style="color:#7a93ab">{status_str}{email_str}</small>
            </div>""", unsafe_allow_html=True)
            if a["approved"] == 0:
                if st.button("Zrušit žádost", key=f"del_abs_{a['id']}"):
                    delete_absence(a["id"])
                    st.rerun()


# ─────────────────────────────────────────────
# PAGE: TIME CORRECTIONS
# ─────────────────────────────────────────────
def page_corrections():
    user = st.session_state.user
    st.markdown("""<div class="page-header">
        <h1>✏️ Úpravy záznamu</h1>
        <p>Žádost o opravu příchodu, odchodu nebo pauzy – schvaluje administrátor</p>
    </div>""", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["➕ Nová žádost o úpravu", "📋 Moje žádosti"])

    with tab1:
        st.markdown("Vyplňte datum a požadované časy. Administrátor žádost schválí nebo zamítne.")
        corr_date = st.date_input("Datum záznamu", value=cet_today(),
                                   min_value=cet_today() - timedelta(days=60))
        st.markdown("**Původní časy** (pokud znáte)")
        oc1, oc2 = st.columns(2)
        with oc1:
            orig_in  = st.text_input("Původní příchod", placeholder="08:15", key="orig_in")
            orig_bs  = st.text_input("Původní začátek pauzy", placeholder="12:00", key="orig_bs")
        with oc2:
            orig_out = st.text_input("Původní odchod", placeholder="16:00", key="orig_out")
            orig_be  = st.text_input("Původní konec pauzy",   placeholder="12:30", key="orig_be")

        st.markdown("**Požadované časy** \\*")
        rc1, rc2 = st.columns(2)
        with rc1:
            req_in  = st.text_input("Požadovaný příchod *", placeholder="07:45", key="req_in")
            req_bs  = st.text_input("Požadovaný začátek pauzy", placeholder="11:30", key="req_bs")
        with rc2:
            req_out = st.text_input("Požadovaný odchod *", placeholder="15:30", key="req_out")
            req_be  = st.text_input("Požadovaný konec pauzy",   placeholder="12:00", key="req_be")

        reason = st.text_area("Důvod úpravy *", placeholder="Popište důvod požadované opravy záznamu…")

        if st.button("Odeslat žádost o úpravu", type="primary"):
            if not req_in or not req_out or not reason.strip():
                st.error("Vyplňte povinná pole: Požadovaný příchod, odchod a důvod.")
            else:
                request_correction(
                    user["id"], corr_date.isoformat(),
                    orig_in, orig_out, orig_bs, orig_be,
                    req_in, req_out, req_bs, req_be, reason
                )
                st.success("Žádost odeslána – administrátor ji brzy vyřídí ✓")
                st.rerun()

    with tab2:
        corrections = get_user_corrections(user["id"])
        if not corrections:
            st.info("Žádné žádosti o úpravu.")
        for c in corrections:
            orig_str = f"{c['orig_in'] or '?'} – {c['orig_out'] or '?'}"
            req_str  = f"{c['req_in']} – {c['req_out']}"
            admin_note_str = f"<br><small style='color:#7a93ab'>Poznámka admina: {c['admin_note']}</small>" if c.get("admin_note") else ""
            st.markdown(f"""<div class="card">
                <div style="display:flex;justify-content:space-between;align-items:flex-start">
                    <div>
                        <strong style="color:#1a2e4a">{c['date']}</strong>
                        <span style="color:#3a5068"> · původně {orig_str} → požadováno {req_str}</span><br>
                        <small style="color:#7a93ab">{c['reason']}</small>{admin_note_str}
                    </div>
                    {correction_status_badge(c['status'])}
                </div>
            </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# PAGE: REPORTS
# ─────────────────────────────────────────────
def page_reports():
    user     = st.session_state.user
    is_admin = user["role"] == "admin"
    st.markdown("""<div class="page-header">
        <h1>📈 Výkazy docházky</h1>
        <p>Měsíční přehled odpracovaných hodin</p>
    </div>""", unsafe_allow_html=True)

    today = cet_today()
    c1, c2, c3 = st.columns(3)
    with c1:
        month = st.selectbox("Měsíc", list(range(1, 13)), index=today.month - 1,
                             format_func=lambda m: MONTH_NAMES[m-1])
    with c2:
        year = st.selectbox("Rok", list(range(today.year - 1, today.year + 1)), index=1)
    with c3:
        if is_admin:
            users = get_all_users()
            uid_opts = {u["id"]: u["display_name"] for u in users}
            uid_opts[0] = "— Všichni zaměstnanci —"
            sel_uid = st.selectbox("Zaměstnanec", options=[0] + [u["id"] for u in users],
                                   format_func=lambda x: uid_opts[x])
        else:
            sel_uid = user["id"]
            st.text_input("Zaměstnanec", value=user["display_name"], disabled=True)

    if is_admin and sel_uid == 0:
        target_users = get_all_users()
    else:
        target_users = [next(u for u in get_all_users() if u["id"] == (sel_uid or user["id"]))]

    all_rows = []
    for tu in target_users:
        stats    = get_month_stats(tu["id"], year, month)
        workdays = count_workdays_so_far(year, month)
        wd_sec   = sum(s["worked_seconds"] for s in stats if not s["is_weekend"])
        we_sec   = sum(s["worked_seconds"] for s in stats if s["is_weekend"])
        expected = workdays * 8 * 3600
        all_rows.append({
            "Jméno": tu["display_name"],
            "Pracovní dny": workdays,
            "Fond (h)": round(expected / 3600, 2),
            "Odpracováno (h)": round(wd_sec / 3600, 2),
            "Víkend (h)": round(we_sec / 3600, 2),
            "Celkem (h)": round((wd_sec + we_sec) / 3600, 2),
            "Saldo (h)": round((wd_sec - expected) / 3600, 2),
        })

    if all_rows:
        df = pd.DataFrame(all_rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
        csv = df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Přehled", index=False)
            for tu in target_users:
                stats = get_month_stats(tu["id"], year, month)
                if stats:
                    df2 = pd.DataFrame(stats)
                    df2["Odpracováno"] = df2["worked_seconds"].apply(seconds_to_hm)
                    df2["Typ"] = df2["is_weekend"].apply(lambda x: "Víkend" if x else "Pracovní")
                    df2 = df2[["date","checkin","checkout","Odpracováno","Typ"]].rename(
                        columns={"date":"Datum","checkin":"Příchod","checkout":"Odchod"})
                    df2.to_excel(writer, sheet_name=tu["display_name"][:31], index=False)
        buf.seek(0)
        dl1, dl2, _ = st.columns([1, 1, 4])
        with dl1:
            st.download_button("⬇ CSV", data=csv,
                               file_name=f"dochazka_{year}_{month:02d}.csv", mime="text/csv")
        with dl2:
            st.download_button("⬇ XLSX", data=buf,
                               file_name=f"dochazka_{year}_{month:02d}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        if len(target_users) == 1:
            st.markdown("---")
            st.markdown("#### Denní přehled")
            stats = get_month_stats(target_users[0]["id"], year, month)
            if stats:
                df3 = pd.DataFrame(stats)
                df3["Odpracováno"] = df3["worked_seconds"].apply(seconds_to_hm)
                df3["Typ"] = df3["is_weekend"].apply(lambda x: "Víkend" if x else "Pracovní")
                df3 = df3[["date","checkin","checkout","Odpracováno","Typ"]].rename(
                    columns={"date":"Datum","checkin":"Příchod","checkout":"Odchod"})
                st.dataframe(df3, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────
# PAGE: ADMIN
# ─────────────────────────────────────────────
def page_admin():
    st.markdown("""<div class="page-header">
        <h1>⚙️ Správa</h1>
        <p>Uživatelé, schválení absencí a úprav docházky</p>
    </div>""", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "👥 Uživatelé", "➕ Nový uživatel",
        "🤒 Vložit nemoc", "✅ Schválení absencí", "✏️ Schválení úprav"
    ])

    # ── Tab 1: Users ──────────────────────────────────────
    with tab1:
        users = get_all_users()
        for u in users:
            with st.expander(f"{u['display_name']} (@{u['username']}) · {u['role']}"):
                # Rename
                st.markdown("**Přejmenování**")
                col_rn1, col_rn2 = st.columns([3, 1])
                with col_rn1:
                    new_name = st.text_input("Nové zobrazované jméno", value=u["display_name"],
                                             key=f"rename_{u['id']}")
                with col_rn2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Přejmenovat", key=f"do_rename_{u['id']}"):
                        if new_name.strip() and new_name.strip() != u["display_name"]:
                            update_user_name(u["id"], new_name)
                            # Update session user if renaming self
                            if u["id"] == st.session_state.user["id"]:
                                st.session_state.user["display_name"] = new_name.strip()
                            st.success(f"Jméno změněno na: {new_name.strip()}")
                            st.rerun()
                        else:
                            st.info("Zadejte jiné jméno.")

                st.markdown("---")
                # Password
                st.markdown("**Změna hesla**")
                col_pw1, col_pw2 = st.columns([3, 1])
                with col_pw1:
                    new_pw = st.text_input("Nové heslo", key=f"pw_{u['id']}", type="password")
                with col_pw2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Změnit heslo", key=f"chpw_{u['id']}"):
                        if new_pw:
                            update_user_password(u["id"], new_pw)
                            st.success("Heslo změněno.")
                        else:
                            st.warning("Zadejte nové heslo.")

                # Deactivate
                if u["id"] != st.session_state.user["id"]:
                    st.markdown("---")
                    if st.button("⛔ Deaktivovat účet", key=f"del_{u['id']}"):
                        deactivate_user(u["id"])
                        st.warning(f"Účet @{u['username']} byl deaktivován.")
                        st.rerun()

    # ── Tab 2: New user ───────────────────────────────────
    with tab2:
        with st.form("new_user_form"):
            c1, c2 = st.columns(2)
            with c1:
                new_username = st.text_input("Uživatelské jméno")
                new_display  = st.text_input("Celé jméno")
                new_color    = st.color_picker("Barva avataru", value="#1f5e8c")
            with c2:
                new_password = st.text_input("Heslo", type="password")
                new_role     = st.selectbox("Role", ["user", "admin"])
                new_email    = st.text_input("E-mail (pro notifikace)")
            submitted = st.form_submit_button("Vytvořit uživatele", type="primary")
        if submitted:
            if new_username and new_password and new_display:
                ok, msg = create_user(new_username, new_password, new_display, new_role, new_color)
                # Store email too if provided
                if ok and new_email:
                    with get_conn() as conn:
                        conn.execute("UPDATE users SET email=? WHERE username=?", (new_email, new_username))
                        conn.commit()
                st.success(msg) if ok else st.error(msg)
            else:
                st.warning("Vyplňte všechna povinná pole.")

    # ── Tab 3: Admin insert sick ──────────────────────────
    with tab3:
        st.markdown("Administrátor může přímo zaznamenat nemoc. Absence bude automaticky schválena.")
        users = get_all_users()
        uid_map = {u["id"]: u["display_name"] for u in users}
        with st.form("admin_sick_form"):
            sick_uid = st.selectbox("Zaměstnanec", [u["id"] for u in users],
                                    format_func=lambda x: uid_map[x])
            c1, c2 = st.columns(2)
            with c1:
                sick_from = st.date_input("Od", value=cet_today())
            with c2:
                sick_to   = st.date_input("Do", value=cet_today())
            sick_note = st.text_input("Poznámka", placeholder="neschopenka, karanténa…")
            submitted_sick = st.form_submit_button("🤒 Zaznamenat nemoc", type="primary")
        if submitted_sick:
            if sick_to < sick_from:
                st.error("Datum 'Do' musí být ≥ 'Od'.")
            else:
                with get_conn() as conn:
                    conn.execute(
                        "INSERT INTO absences(user_id,absence_type,date_from,date_to,note,approved,email_sent) VALUES(?,?,?,?,?,1,0)",
                        (sick_uid, "sickday", sick_from.isoformat(), sick_to.isoformat(), sick_note)
                    )
                    conn.commit()
                days = (sick_to - sick_from).days + 1
                st.success(f"Nemoc pro **{uid_map[sick_uid]}** zaznamenána ({days} {'den' if days==1 else 'dní'}) ✓")
                st.rerun()

        st.markdown("---")
        st.markdown("**Nedávné záznamy nemoci**")
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
            day_label = r["date_from"] if days == 1 else f"{r['date_from']} – {r['date_to']}"
            st.markdown(f"""<div class="card card-red" style="padding:12px 18px;margin-bottom:6px">
                <strong style="color:#1a2e4a">{r['display_name']}</strong>
                <span style="color:#c0392b"> · 🤒</span>
                <span style="color:#3a5068"> {day_label}{note_str}</span>
            </div>""", unsafe_allow_html=True)
            if st.button("🗑 Smazat", key=f"del_sick_{r['id']}"):
                delete_absence(r["id"])
                st.rerun()

    # ── Tab 4: Approve absences ───────────────────────────
    with tab4:
        with get_conn() as conn:
            pending_abs = [dict(r) for r in conn.execute(
                """SELECT a.*, u.display_name, u.email FROM absences a
                   JOIN users u ON a.user_id=u.id
                   WHERE a.approved=0 ORDER BY a.date_from"""
            ).fetchall()]

        if not pending_abs:
            st.info("✅ Žádné čekající žádosti o absenci.")

        type_labels = {"sickday": "🤒 Sickday", "vacation": "🏖 Dovolená"}
        for a in pending_abs:
            type_label = type_labels.get(a["absence_type"], a["absence_type"])
            date_str   = a["date_from"] if a["date_from"] == a["date_to"] else f"{a['date_from']} – {a['date_to']}"
            email_info = a.get("email") or ""
            st.markdown(f"""<div class="card card-yellow">
                <strong style="color:#1a2e4a">{a['display_name']}</strong>
                <span style="color:#3a5068"> · {type_label} · {date_str}</span>
                <span style="color:#7a93ab">{' · ' + a['note'] if a.get('note') else ''}</span><br>
                <small style="color:#7a93ab">✉ Po schválení bude odeslán email na: <strong>{email_info or 'email nenastavena'}</strong></small>
            </div>""", unsafe_allow_html=True)
            col1, col2, _ = st.columns([1, 1, 4])
            with col1:
                if st.button("✅ Schválit", key=f"app_abs_{a['id']}"):
                    sent = approve_absence(a["id"], True,
                                           user_email=email_info,
                                           user_name=a["display_name"])
                    if sent:
                        st.success(f"Schváleno ✓ · Email odeslán na {email_info}" if email_info
                                   else "Schváleno ✓ (simulace emailu – email uživatele není nastaven)")
                    else:
                        st.success("Schváleno ✓")
                    st.rerun()
            with col2:
                if st.button("❌ Zamítnout", key=f"rej_abs_{a['id']}"):
                    approve_absence(a["id"], False)
                    st.rerun()

        # Show email simulation log
        if st.session_state.get("email_log"):
            st.markdown("---")
            st.markdown("**📬 Simulace odeslaných e-mailů** *(EMAIL_ENABLED = False)*")
            for em in st.session_state["email_log"]:
                with st.expander(f"✉ {em['to']} – {em['subject']}"):
                    st.code(em["body"])

    # ── Tab 5: Approve corrections ────────────────────────
    with tab5:
        pending_corr = get_pending_corrections()
        if not pending_corr:
            st.info("✅ Žádné čekající žádosti o úpravu záznamu.")

        for c in pending_corr:
            orig_str = f"{c['orig_in'] or '?'} – {c['orig_out'] or '?'}"
            req_str  = f"{c['req_in']} – {c['req_out']}"
            brk_str  = f" · pauza {c['req_break_start']}–{c['req_break_end']}" if c.get("req_break_start") else ""
            st.markdown(f"""<div class="card card-yellow">
                <strong style="color:#1a2e4a">{c['display_name']}</strong>
                <span style="color:#3a5068"> · {c['date']} · původně {orig_str} → požadováno {req_str}{brk_str}</span><br>
                <small style="color:#7a93ab">{c['reason']}</small>
            </div>""", unsafe_allow_html=True)

            admin_note_key = f"corr_note_{c['id']}"
            admin_note = st.text_input("Poznámka pro zaměstnance (volitelné)", key=admin_note_key)
            col1, col2, _ = st.columns([1, 1, 4])
            with col1:
                if st.button("✅ Schválit", key=f"app_corr_{c['id']}"):
                    resolve_correction(c["id"], True, admin_note)
                    st.success("Úprava schválena ✓")
                    st.rerun()
            with col2:
                if st.button("❌ Zamítnout", key=f"rej_corr_{c['id']}"):
                    resolve_correction(c["id"], False, admin_note)
                    st.rerun()
            st.markdown("---")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
init_db()

# Add email column to users if not exists (migration)
with get_conn() as _conn:
    try:
        _conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        _conn.commit()
    except Exception:
        pass

if "user" not in st.session_state:
    page_login()
else:
    user     = st.session_state.user
    is_admin = user["role"] == "admin"

    with st.sidebar:
        # ── Logo (modré – světlé pozadí sidebaru) ──
        st.markdown(f"""
        <div style="padding:20px 16px 12px;border-bottom:1px solid var(--border)">
            {logo_img_tag(white=False, height=44)}
            <div style="font-size:.72rem;color:#94a3b8;margin-top:6px;font-weight:500">
                Docházkový systém
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── User chip ──
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;
                    padding:14px 16px 10px;border-bottom:1px solid var(--border)">
            <div style="width:32px;height:32px;border-radius:16px;
                        background:{'linear-gradient(120deg,#0b5390,#158bc8)' if is_admin else '#e0f2fe'};
                        display:flex;align-items:center;justify-content:center;
                        color:{'#fff' if is_admin else '#1f5e8c'};
                        font-weight:800;font-size:.85rem;flex-shrink:0">
                {user['display_name'][0].upper()}
            </div>
            <div>
                <div style="font-weight:700;font-size:.875rem;color:#1e293b;line-height:1.2">
                    {user['display_name']}
                </div>
                <div style="font-size:.72rem;color:#94a3b8">
                    {'Administrátor' if is_admin else 'Zaměstnanec'}
                </div>
            </div>
        </div>
        <div style="height:12px"></div>
        """, unsafe_allow_html=True)

        if "page" not in st.session_state:
            st.session_state.page = "dashboard"

        pages = {
            "📊 Přehled dne":     "dashboard",
            "🕐 Moje docházka":   "attendance",
            "🏖 Absence":         "absences",
            "✏️ Úpravy záznamu":  "corrections",
            "📈 Výkazy":          "reports",
        }
        if is_admin:
            pages["⚙️ Správa"] = "admin"

        for label, key in pages.items():
            if st.button(label, use_container_width=True,
                         type="primary" if st.session_state.page == key else "secondary"):
                st.session_state.page = key
                st.rerun()

        st.markdown(f"""
        <div style="height:1px;background:var(--border);margin:8px 0 10px"></div>
        <div style="font-size:.7rem;color:#94a3b8;text-align:center;padding:4px 0 8px;
                    font-variant-numeric:tabular-nums">
            ⏱ CET: {cet_now().strftime("%d.%m.%Y %H:%M")}
        </div>
        """, unsafe_allow_html=True)
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
    elif page == "corrections":
        page_corrections()
    elif page == "reports":
        page_reports()
    elif page == "admin" and is_admin:
        page_admin()

    # ── Footer – shodný s JSX ──────────────────────────────
    st.markdown(f"""
    <div style="background:linear-gradient(120deg,#0b5390 0%,#158bc8 81%);
                color:rgba(255,255,255,.7);
                padding:16px 48px;margin-top:48px;
                display:flex;align-items:center;justify-content:space-between;
                font-size:.75rem;border-radius:14px;">
        <div style="display:flex;align-items:center;gap:12px">
            {logo_img_tag(white=True, height=28)}
            <span>Exekutorský úřad Praha 4 – Mgr. Jan Škarpa</span>
        </div>
        <span>© {cet_now().year} eupraha.cz</span>
    </div>
    """, unsafe_allow_html=True)
