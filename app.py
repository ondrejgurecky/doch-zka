import streamlit as st
import streamlit.components.v1 as _components
import sqlite3
import pandas as pd
import hashlib
import json
import os
import io
import base64
import threading
import shutil
import glob
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date, timedelta, time
from pathlib import Path
from zoneinfo import ZoneInfo

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
DB_PATH    = Path(__file__).parent / "dochazka.db"
BACKUP_DIR = Path(__file__).parent / "backups"
BACKUP_DIR.mkdir(exist_ok=True)
BACKUP_KEEP = 30      # max počet uchovávaných automatických záloh
BACKUP_INTERVAL_H = 6 # každých N hodin
_BACKUP_STARTED    = False  # module-level – zabrání duplicitním threadům
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

/* ═══════════════════════════════════════════════
   1.  HIDE ALL STREAMLIT CHROME
   ═══════════════════════════════════════════════ */
#MainMenu, header[data-testid="stHeader"],
footer, [data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
button[title="View fullscreen"],
.stDeployButton { display: none !important; visibility: hidden !important; }

/* Remove top padding left by hidden header */
.main > div:first-child { padding-top: 0 !important; }
.block-container { padding-top: 0 !important; padding-bottom: 2rem !important; }

/* ═══════════════════════════════════════════════
   2.  DESIGN TOKENS  (identical to JSX)
   ═══════════════════════════════════════════════ */
:root {
    --primary:    #1f5e8c;
    --primary-d:  #0b5390;
    --bright:     #158bc8;
    --gradient:   linear-gradient(120deg, #0b5390 0%, #158bc8 81%);
    --white:      #ffffff;
    --bg:         #f8fafc;
    --border:     #e2e8f0;
    --text-dark:  #1e293b;
    --text-body:  #475569;
    --text-muted: #64748b;
    --green:      #065f46;
    --green-bg:   #d1fae5;
    --red:        #991b1b;
    --red-bg:     #fee2e2;
    --orange:     #92400e;
    --orange-bg:  #fef3c7;
    --blue-bg:    #e0f2fe;
    --r:          8px;
    --R:          14px;
    --sh:         0 1px 4px rgba(31,94,140,.07);
}

/* ═══════════════════════════════════════════════
   3.  BASE
   ═══════════════════════════════════════════════ */
html, body, [class*="css"] {
    font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
    -webkit-font-smoothing: antialiased !important;
}
.stApp { background: var(--bg) !important; }

/* ═══════════════════════════════════════════════
   4.  SIDEBAR  – matches JSX <aside>
       width 240px, white, border-right
   ═══════════════════════════════════════════════ */
[data-testid="stSidebar"] {
    background: var(--white) !important;
    border-right: 1px solid var(--border) !important;
    min-width: 240px !important;
    max-width: 240px !important;
    padding: 0 !important;
}
/* Remove inner Streamlit padding */
[data-testid="stSidebar"] > div:first-child {
    padding: 0 !important;
}
[data-testid="stSidebar"] .block-container {
    padding: 0 !important;
}
/* Collapse arrow – hide it */
[data-testid="stSidebarCollapseButton"] { display: none !important; }

/* Nav buttons – match JSX sidebar buttons exactly */
[data-testid="stSidebar"] .stButton > button {
    display: flex !important;
    align-items: center !important;
    justify-content: flex-start !important;
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
    margin-bottom: 4px !important;
    transition: background .15s, color .15s !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: var(--bg) !important;
    color: var(--text-dark) !important;
}
/* Active = kind="primary" */
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: #e8f4fd !important;
    color: var(--primary) !important;
    font-weight: 700 !important;
}

/* ═══════════════════════════════════════════════
   5.  MAIN CONTENT  –  strip Streamlit padding
   ═══════════════════════════════════════════════ */
.main .block-container,
[data-testid="stAppViewContainer"] > section > div,
section.main > div:first-child {
    max-width: 100% !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
}
/* Streamlit sometimes uses these selectors */
div[data-testid="stVerticalBlock"] > div > div > div {
    padding-left: 0 !important;
    padding-right: 0 !important;
}

/* ═══════════════════════════════════════════════
   6.  PAGE SECTION HEADER  (JSX SectionHeader)
       Full-width, no rounded corners – exact match
   ═══════════════════════════════════════════════ */
.page-header {
    background: var(--gradient);
    padding: 40px 48px 32px;
    margin-bottom: 0;
    position: relative;
    overflow: hidden;
}
.page-header h1 {
    font-size: 1.625rem !important;
    font-weight: 800 !important;
    color: #fff !important;
    margin: 0 0 6px !important;
    line-height: 1.2 !important;
    letter-spacing: -.3px !important;
}
.page-header p { font-size: .875rem; color: rgba(255,255,255,.8); margin: 0; }

/* Content padding  –  mirrors JSX  padding: 32px 48px */
.content-pad { padding: 32px 48px; }

/* ═══════════════════════════════════════════════
   7.  CARDS  (JSX Card component)
   ═══════════════════════════════════════════════ */
.card {
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: var(--R);
    padding: 20px 24px;
    margin-bottom: 14px;
    box-shadow: var(--sh);
}
.card-green  { border-left: 4px solid #059669; }
.card-yellow { border-left: 4px solid #d97706; }
.card-red    { border-left: 4px solid #dc2626; }
.card-blue   { border-left: 4px solid var(--primary); }
.card-gray   { border-left: 4px solid #94a3b8; }
.card h3 {
    margin: 0 0 6px; font-size: .7rem; color: var(--text-muted);
    font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
}
.card .value {
    font-size: 1.875rem; font-weight: 800; color: var(--text-dark);
    font-variant-numeric: tabular-nums; line-height: 1.1;
}
.card .sub { font-size: .75rem; color: var(--text-muted); margin-top: 4px; }

/* ═══════════════════════════════════════════════
   8.  BADGES  (JSX Badge)
   ═══════════════════════════════════════════════ */
.badge {
    display: inline-block; padding: 2px 8px;
    border-radius: 6px; font-size: .6875rem; font-weight: 700;
}
.badge-working  { background: var(--green-bg);  color: var(--green); }
.badge-pause    { background: var(--orange-bg); color: var(--orange); }
.badge-sick     { background: var(--red-bg);    color: var(--red); }
.badge-nemoc    { background: #ffe4e6;          color: #9f1239; }
.badge-vacation { background: var(--blue-bg);   color: var(--primary); }
.badge-offline  { background: #f1f5f9;          color: #64748b; }
.badge-pending  { background: var(--orange-bg); color: var(--orange); }
.badge-approved { background: var(--green-bg);  color: var(--green); }
.badge-rejected { background: var(--red-bg);    color: var(--red); }

/* ═══════════════════════════════════════════════
   9.  PERSON ROWS
   ═══════════════════════════════════════════════ */
.person-row {
    display: flex; align-items: center; gap: 14px;
    padding: 12px 18px;
    background: var(--white); border: 1px solid var(--border);
    border-radius: var(--R); margin-bottom: 8px; box-shadow: var(--sh);
}
.avatar {
    width: 40px; height: 40px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: .9rem; flex-shrink: 0;
}
.person-row .name   { font-weight: 700; font-size: .9rem;  color: var(--text-dark); }
.person-row .detail { font-size: .76rem; color: var(--text-muted); }

/* ═══════════════════════════════════════════════
   10.  GLOBAL BUTTONS  (JSX Btn)
   ═══════════════════════════════════════════════ */
.stButton > button {
    background: var(--white) !important;
    color: var(--primary) !important;
    border: 1.5px solid var(--border) !important;
    border-radius: var(--r) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: .875rem !important;
    padding: 8px 18px !important;
    transition: all .15s !important;
    box-shadow: none !important;
}
.stButton > button:hover {
    background: var(--bg) !important;
    border-color: var(--primary) !important;
}
/* Primary = gradient  */
.stButton > button[kind="primary"] {
    background: var(--gradient) !important;
    color: #fff !important;
    border: none !important;
}
.stButton > button[kind="primary"]:hover { opacity: .92 !important; }

/* Coloured variants */
.btn-green  > button { background: var(--green-bg)  !important; color: var(--green)  !important; border-color: #6ee7b7 !important; }
.btn-red    > button { background: var(--red-bg)    !important; color: var(--red)    !important; border-color: #fca5a5 !important; }
.btn-yellow > button { background: var(--orange-bg) !important; color: var(--orange) !important; border-color: #fcd34d !important; }
.btn-green  > button:hover { background: #a7f3d0 !important; }
.btn-red    > button:hover { background: #fecaca !important; }
.btn-yellow > button:hover { background: #fde68a !important; }

/* ═══════════════════════════════════════════════
   11.  FORM INPUTS
   ═══════════════════════════════════════════════ */
.stTextInput input,
.stSelectbox > div[data-baseweb],
.stDateInput input,
.stTextArea textarea,
.stNumberInput input {
    background: var(--white) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r) !important;
    color: var(--text-dark) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: .875rem !important;
    padding: 9px 12px !important;
}
.stTextInput input:focus,
.stTextArea textarea:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px rgba(31,94,140,.1) !important;
    outline: none !important;
}
label,
.stSelectbox label, .stTextInput label,
.stDateInput label, .stTextArea label {
    color: var(--text-body) !important;
    font-weight: 600 !important;
    font-size: .8125rem !important;
}

/* ═══════════════════════════════════════════════
   12.  TABS
   ═══════════════════════════════════════════════ */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid var(--border) !important;
    gap: 0 !important;
    margin-bottom: 20px !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--text-muted) !important;
    font-weight: 600 !important; font-size: .875rem !important;
    border-bottom: 2px solid transparent !important;
    padding: 10px 18px !important; margin-bottom: -1px !important;
}
.stTabs [aria-selected="true"] {
    color: var(--primary) !important;
    border-bottom: 2px solid var(--primary) !important;
    background: transparent !important;
}

/* ═══════════════════════════════════════════════
   13.  TABLE / DATAFRAME
   ═══════════════════════════════════════════════ */
.stDataFrame {
    border: 1px solid var(--border) !important;
    border-radius: var(--R) !important;
    overflow: hidden !important;
    box-shadow: var(--sh) !important;
}

/* ═══════════════════════════════════════════════
   14.  ALERTS
   ═══════════════════════════════════════════════ */
div[data-testid="stAlert"] {
    border-radius: var(--r) !important;
    font-size: .875rem !important;
    font-family: 'Inter', sans-serif !important;
}
.stSuccess, [data-testid="stAlert"][kind="success"] {
    background: var(--green-bg) !important; color: var(--green) !important;
}
.stInfo, [data-testid="stAlert"][kind="info"] {
    background: var(--blue-bg) !important; color: var(--primary) !important;
}
.stWarning, [data-testid="stAlert"][kind="warning"] {
    background: var(--orange-bg) !important; color: var(--orange) !important;
}
.stError, [data-testid="stAlert"][kind="error"] {
    background: var(--red-bg) !important; color: var(--red) !important;
}

/* ═══════════════════════════════════════════════
   15.  EXPANDER
   ═══════════════════════════════════════════════ */
details summary,
.streamlit-expanderHeader {
    background: var(--white) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r) !important;
    color: var(--text-dark) !important;
    font-weight: 700 !important; font-size: .875rem !important;
    padding: 12px 16px !important;
}

/* ═══════════════════════════════════════════════
   16.  MISC
   ═══════════════════════════════════════════════ */
hr { border-color: var(--border) !important; }
.sidebar-divider { height: 1px; background: var(--border); margin: 10px 0; }

/* ── Inline table rows (JSX-style) ── */
.row-table {
    width: 100%;
    border-collapse: collapse;
    font-size: .8125rem;
}
.row-table th {
    padding: 10px 16px;
    text-align: left;
    font-size: .6875rem;
    font-weight: 700;
    color: var(--text-muted);
    letter-spacing: .5px;
    text-transform: uppercase;
    border-bottom: 1px solid var(--border);
    background: #f8fafc;
}
.row-table td {
    padding: 10px 16px;
    border-bottom: 1px solid #f1f5f9;
    color: var(--text-body);
}
.row-table tr:last-child td { border-bottom: none; }
.row-table tr:nth-child(even) td { background: #f8fafc; }

/* ── Clock big number ── */
.clock-big {
    font-size: 2.25rem;
    font-weight: 800;
    color: var(--primary);
    font-variant-numeric: tabular-nums;
    letter-spacing: -1px;
    line-height: 1;
}
.clock-label {
    font-size: .6875rem; font-weight: 700;
    color: var(--text-muted); text-transform: uppercase;
    letter-spacing: .08em; margin-bottom: 4px;
}

/* ── Inline section title (not a full banner) ── */
.section-title {
    font-size: .9375rem; font-weight: 700;
    color: var(--text-dark); margin-bottom: 14px;
}
.divider { height: 1px; background: var(--border); margin: 24px 0; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# DATABASE

# ─────────────────────────────────────────────
# AUTOMATICKÁ ZÁLOHA
# ─────────────────────────────────────────────
def _do_backup(label: str = "auto") -> Path | None:
    """Zkopíruje DB do BACKUP_DIR. Vrátí cestu k záloze nebo None."""
    if not DB_PATH.exists():
        return None
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"dochazka_{label}_{ts}.sqlite"
    try:
        # Použij SQLite Online Backup API – bezpečné za provozu
        src_conn = sqlite3.connect(DB_PATH)
        dst_conn = sqlite3.connect(dest)
        src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()
        # Udržuj max BACKUP_KEEP souborů pro každý label
        pattern = str(BACKUP_DIR / f"dochazka_{label}_*.sqlite")
        old = sorted(glob.glob(pattern))
        for f in old[:-BACKUP_KEEP]:
            try: os.remove(f)
            except Exception: pass
        return dest
    except Exception:
        return None


def _auto_backup_loop():
    """Běží v daemon threadu; zálohuje každých BACKUP_INTERVAL_H hodin."""
    import time
    while True:
        time.sleep(BACKUP_INTERVAL_H * 3600)
        _do_backup("auto")


def start_auto_backup():
    """Spustí background thread pro automatické zálohy – pouze jednou za proces."""
    global _BACKUP_STARTED
    if not _BACKUP_STARTED:
        _BACKUP_STARTED = True
        t = threading.Thread(target=_auto_backup_loop, daemon=True)
        t.start()


def list_backups() -> list[dict]:
    """Vrátí seznam všech záloh seřazených od nejnovější."""
    files = sorted(glob.glob(str(BACKUP_DIR / "dochazka_*.sqlite")), reverse=True)
    result = []
    for f in files:
        p    = Path(f)
        size = p.stat().st_size
        name = p.name  # dochazka_auto_20250227_143000.sqlite
        parts = name.replace(".sqlite", "").split("_")
        # parts: ['dochazka', label, date, time]
        label = parts[1] if len(parts) >= 4 else "?"
        result.append({"path": f, "name": p.name, "size": size, "label": label})
    return result


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
        CREATE TABLE IF NOT EXISTS leave_funds (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER NOT NULL,
            year           INTEGER NOT NULL,
            vacation_days  INTEGER DEFAULT 20,
            vacation_carry INTEGER DEFAULT 0,
            sickday_days   INTEGER DEFAULT 5,
            UNIQUE(user_id, year),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """)
        for _migration in [
            "ALTER TABLE absences ADD COLUMN email_sent INTEGER DEFAULT 0",
            "ALTER TABLE absences ADD COLUMN half_days TEXT DEFAULT '[]'",
            "ALTER TABLE pauses ADD COLUMN paid INTEGER DEFAULT 0",
        ]:
            try:
                conn.execute(_migration)
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

def update_user_email(user_id, email: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET email=? WHERE id=?", (email.strip(), user_id))
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
    now = now_str()
    if att and att["checkin_time"] and not att["checkout_time"]:
        return False, "Příchod byl již zaznamenán (nejprve zaznamenejte odchod)."
    if att and att["checkin_time"] and att["checkout_time"]:
        # Druhý příchod v tentýž den – mezičas se stane pauzou
        pause_start = att["checkout_time"]
        with get_conn() as conn:
            conn.execute("UPDATE attendance SET checkout_time=NULL WHERE id=?", (att["id"],))
            conn.execute(
                "INSERT INTO pauses(attendance_id,pause_type,start_time,end_time,paid)"
                " VALUES(?,?,?,?,0)",
                (att["id"], "přestávka (2. příchod)", pause_start, now)
            )
            conn.commit()
        return True, f"Druhý příchod zaznamenán ✓ (přestávka {pause_start[11:16]}–{now[11:16]} přidána)"
    att_id = ensure_attendance(user_id)
    with get_conn() as conn:
        conn.execute("UPDATE attendance SET checkin_time=? WHERE id=?", (now, att_id))
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

def open_pause(att_id, pause_type, paid=False, start_override=None):
    pauses = get_pauses(att_id)
    for p in pauses:
        if p["end_time"] is None:
            return False, "Existuje nezavřená pauza."
    start = start_override or now_str()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO pauses(attendance_id,pause_type,start_time,paid) VALUES(?,?,?,?)",
            (att_id, pause_type, start, 1 if paid else 0)
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
def request_absence(user_id, absence_type, date_from, date_to, note="", half_days=None):
    hd_json = json.dumps([d.isoformat() if hasattr(d, 'isoformat') else d
                          for d in (half_days or [])])
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO absences(user_id,absence_type,date_from,date_to,note,half_days)"
            " VALUES(?,?,?,?,?,?)",
            (user_id, absence_type, date_from.isoformat(), date_to.isoformat(), note, hd_json)
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
def update_nemoc_end(absence_id: int, date_to):
    """Doplní konec nemoci do existujícího záznamu."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE absences SET date_to=? WHERE id=? AND absence_type='nemoc'",
            (date_to.isoformat(), absence_id)
        )
        conn.commit()


# ── Fondy dovolené / sickday ─────────────────────────────────────
def ensure_leave_fund(user_id: int, year: int) -> dict:
    """Vrátí (nebo vytvoří) fond pro uživatele+rok."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM leave_funds WHERE user_id=? AND year=?", (user_id, year)
        ).fetchone()
        if row:
            return dict(row)
        conn.execute(
            "INSERT INTO leave_funds(user_id,year,vacation_days,vacation_carry,sickday_days)"
            " VALUES(?,?,20,0,5)",
            (user_id, year)
        )
        conn.commit()
        return {"user_id": user_id, "year": year,
                "vacation_days": 20, "vacation_carry": 0, "sickday_days": 5}


def get_leave_fund(user_id: int, year: int) -> dict:
    return ensure_leave_fund(user_id, year)


def update_leave_fund(user_id: int, year: int,
                      vacation_days: int = None,
                      vacation_carry: int = None,
                      sickday_days: int = None):
    fund = ensure_leave_fund(user_id, year)
    vd = vacation_days  if vacation_days  is not None else fund["vacation_days"]
    vc = vacation_carry if vacation_carry is not None else fund["vacation_carry"]
    sd = sickday_days   if sickday_days   is not None else fund["sickday_days"]
    with get_conn() as conn:
        conn.execute(
            "UPDATE leave_funds SET vacation_days=?, vacation_carry=?, sickday_days=?"
            " WHERE user_id=? AND year=?",
            (vd, vc, sd, user_id, year)
        )
        conn.commit()


def get_used_vacation(user_id: int, year: int) -> float:
    """Čerpáno dní dovolené v roce (vacation_half = 0.5)."""
    first = date(year, 1, 1)
    last  = date(year, 12, 31)
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT absence_type, date_from, date_to FROM absences
               WHERE user_id=? AND approved=1
               AND absence_type IN ('vacation','vacation_half')
               AND date_from >= ? AND date_to <= ?""",
            (user_id, first.isoformat(), last.isoformat())
        ).fetchall()
    total = 0.0
    for r in rows:
        if r["absence_type"] == "vacation_half":
            total += 0.5
        else:
            af = date.fromisoformat(r["date_from"])
            at = date.fromisoformat(r["date_to"])
            total += count_workdays_in_range(af, at)
    return total


def get_used_sickdays(user_id: int, year: int) -> int:
    """Čerpáno sickday dní v roce."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT date_from, date_to FROM absences
               WHERE user_id=? AND approved=1 AND absence_type='sickday'
               AND date_from >= ? AND date_to <= ?""",
            (user_id, date(year, 1, 1).isoformat(), date(year, 12, 31).isoformat())
        ).fetchall()
    total = 0
    for r in rows:
        af = date.fromisoformat(r["date_from"])
        at = date.fromisoformat(r["date_to"])
        total += count_workdays_in_range(af, at)
    return total


def leave_summary(user_id: int, year: int) -> dict:
    """Kompletní přehled fondů a čerpání pro uživatele+rok."""
    fund      = ensure_leave_fund(user_id, year)
    used_vac  = get_used_vacation(user_id, year)
    used_sick = get_used_sickdays(user_id, year)
    total_vac = fund["vacation_days"] + fund["vacation_carry"]
    return {
        "vacation_total":  total_vac,
        "vacation_used":   used_vac,
        "vacation_remain": total_vac - used_vac,
        "vacation_carry":  fund["vacation_carry"],
        "vacation_base":   fund["vacation_days"],
        "sickday_total":   fund["sickday_days"],
        "sickday_used":    used_sick,
        "sickday_remain":  fund["sickday_days"] - used_sick,
    }


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

def get_pending_counts() -> dict:
    """Vrátí počty čekajících schválení pro notifikační odznak."""
    with get_conn() as conn:
        abs_cnt = conn.execute(
            "SELECT COUNT(*) FROM absences WHERE approved=0"
        ).fetchone()[0]
        cor_cnt = conn.execute(
            "SELECT COUNT(*) FROM time_corrections WHERE status='pending'"
        ).fetchone()[0]
    return {"absences": abs_cnt, "corrections": cor_cnt, "total": abs_cnt + cor_cnt}


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
    type_cz = {"vacation": "Dovolená", "vacation_half": "Dovolená (půlden)", "nemoc": "Nemoc / PN", "sickday": "Sickday"}.get(absence["absence_type"], "Absence")
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

def seconds_to_hm(seconds) -> str:
    seconds = int(max(0, seconds or 0))
    return f"{seconds // 3600}h {(seconds % 3600) // 60:02d}m"

def calc_worked_seconds(att, pauses):
    """Odpracované sekundy. Placené pauzy (lékař) se NEodečítají."""
    if not att or not att["checkin_time"]:
        return 0
    checkout = att["checkout_time"] or now_str()
    total = time_to_seconds(checkout) - time_to_seconds(att["checkin_time"])
    for p in pauses:
        if p.get("paid"):          # placená pauza – nezmenšuje fond
            continue
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

def czech_holidays(year: int) -> set:
    """Státní svátky ČR pro daný rok."""
    a = year % 19
    b, c = divmod(year, 100)
    d2, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d2 - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month_, day_ = divmod(114 + h + l - 7 * m, 31)
    easter_monday = date(year, month_, day_ + 1) + timedelta(days=1)
    return {
        date(year, 1, 1),    # Nový rok
        easter_monday,        # Velikonoční pondělí
        date(year, 5, 1),    # Svátek práce
        date(year, 5, 8),    # Den vítězství
        date(year, 7, 5),    # Cyril a Metoděj
        date(year, 7, 6),    # Mistr Jan Hus
        date(year, 9, 28),   # Den české státnosti
        date(year, 10, 28),  # Vznik ČSR
        date(year, 11, 17),  # Den boje za svobodu a demokracii
        date(year, 12, 24),  # Štědrý den
        date(year, 12, 25),  # 1. svátek vánoční
        date(year, 12, 26),  # 2. svátek vánoční
    }


def is_workday(d: date) -> bool:
    """Pracovní den = ne víkend a ne státní svátek."""
    return d.weekday() < 5 and d not in czech_holidays(d.year)


def count_workdays_in_range(d_from: date, d_to: date) -> int:
    """Počet pracovních dní v rozsahu (včetně krajních, bez víkendů a svátků)."""
    count, d = 0, d_from
    while d <= d_to:
        if is_workday(d):
            count += 1
        d += timedelta(days=1)
    return count


def count_workdays_so_far(year: int, month: int) -> int:
    """Pracovní dny v měsíci do dneška (bez víkendů a státních svátků)."""
    today = cet_today()
    first = date(year, month, 1)
    if year == today.year and month == today.month:
        last = today
    else:
        last = (date(year, month + 1, 1) - timedelta(days=1)) if month < 12 else date(year, 12, 31)
    return count_workdays_in_range(first, last)


def count_absence_workdays(user_id: int, year: int, month: int) -> float:
    """Počet schválených pracovních dní absence v daném měsíci (půlden v half_days = 0.5)."""
    first = date(year, month, 1)
    last  = (date(year, month + 1, 1) - timedelta(days=1)) if month < 12 else date(year, 12, 31)
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT absence_type, date_from, date_to, half_days FROM absences
               WHERE user_id=? AND approved=1
               AND absence_type IN ('vacation','vacation_half','sickday','nemoc')
               AND date_to >= ? AND date_from <= ?""",
            (user_id, first.isoformat(), last.isoformat())
        ).fetchall()
    total = 0.0
    for row in rows:
        if row["absence_type"] == "vacation_half":
            total += 0.5
        elif row["absence_type"] == "vacation":
            hd  = set(json.loads(row["half_days"] or "[]"))
            ab_from = max(date.fromisoformat(row["date_from"]), first)
            ab_to   = min(date.fromisoformat(row["date_to"]),   last)
            cur = ab_from
            while cur <= ab_to:
                if is_workday(cur):
                    total += 0.5 if cur.isoformat() in hd else 1.0
                cur += timedelta(days=1)
        else:
            ab_from = max(date.fromisoformat(row["date_from"]), first)
            ab_to   = min(date.fromisoformat(row["date_to"]),   last)
            total  += count_workdays_in_range(ab_from, ab_to)
    return total


def effective_workdays(user_id: int, year: int, month: int) -> float:
    """Efektivní fond = pracovní dny měsíce − schválené absence (vacation_half = 0.5 dne)."""
    return max(0.0, count_workdays_so_far(year, month) - count_absence_workdays(user_id, year, month))


def get_all_absences_for_calendar(year: int, month: int):
    """Všechny schválené absence v daném měsíci pro kalendář."""
    first = date(year, month, 1)
    last  = (date(year, month + 1, 1) - timedelta(days=1)) if month < 12 else date(year, 12, 31)
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            """SELECT a.*, u.display_name, u.color
               FROM absences a JOIN users u ON a.user_id = u.id
               WHERE a.approved=1
               AND a.absence_type IN ('vacation','vacation_half','sickday','nemoc')
               AND a.date_to >= ? AND a.date_from <= ?
               ORDER BY a.date_from""",
            (first.isoformat(), last.isoformat())
        ).fetchall()]


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


def get_missing_today() -> list:
    """Vrátí uživatele, kteří dnes nemají ani příchod ani absenci."""
    today = today_str()
    absences = {a["user_id"] for a in get_absences_for_date(today)}
    result = []
    for u in get_all_users():
        if u["id"] in absences:
            continue
        att = get_attendance(u["id"], today)
        if not att or not att["checkin_time"]:
            result.append(u)
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
    "sickday": ("Sickday",   "sick"),
    "nemoc":   ("Nemoc/PN", "nemoc"),
    "vacation":("Dovolená",  "vacation"),
    "offline": ("Offline",   "offline"),
    "done":    ("Skončil/a", "offline"),
}
PAUSE_TYPES = ["🍽 Oběd", "☕ Přestávka", "📦 Jiné"]
PAUSE_TYPES_PAID = {"🏥 Lékař (placená pauza)"}  # nezmenšuje odpracovaný čas
MONTH_NAMES = ["Leden","Únor","Březen","Duben","Květen","Červen",
               "Červenec","Srpen","Září","Říjen","Listopad","Prosinec"]

def status_badge(status: str) -> str:
    label, cls = STATUS_LABEL.get(status, ("", "offline"))
    return f'<span class="badge badge-{cls}">{label}</span>'

def nemoc_open_badge():
    return '<span class="badge badge-nemoc">🤒 Otevřená nemoc</span>'

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



# ── Admin – přímá editace docházky ──────────────────────────────
def admin_set_attendance(user_id: int, day: str, checkin: str, checkout: str):
    """Nastaví nebo přepíše příchod/odchod pro libovolného uživatele."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM attendance WHERE user_id=? AND date=?", (user_id, day)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE attendance SET checkin_time=?, checkout_time=? WHERE id=?",
                (checkin or None, checkout or None, row["id"])
            )
        else:
            conn.execute(
                "INSERT INTO attendance(user_id, date, checkin_time, checkout_time)"
                " VALUES(?,?,?,?)",
                (user_id, day, checkin or None, checkout or None)
            )
        conn.commit()


def admin_set_pause(att_id: int, pause_type: str, start: str, end: str):
    """Přidá nebo přepíše pauzu k záznamu docházky."""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO pauses(attendance_id, pause_type, start_time, end_time)"
            " VALUES(?,?,?,?)",
            (att_id, pause_type, start, end or None)
        )
        conn.commit()


def admin_delete_pause(pause_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM pauses WHERE id=?", (pause_id,))
        conn.commit()


def admin_clear_attendance(user_id: int, day: str):
    """Smaže celý záznam docházky včetně pauz."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM attendance WHERE user_id=? AND date=?", (user_id, day)
        ).fetchone()
        if row:
            conn.execute("DELETE FROM pauses WHERE attendance_id=?", (row["id"],))
            conn.execute("DELETE FROM attendance WHERE id=?", (row["id"],))
            conn.commit()

# ─────────────────────────────────────────────
# PAGE: DASHBOARD
# ─────────────────────────────────────────────
def page_dashboard():
    today_cet = cet_today()
    st.markdown(f"""<div class="page-header">
        <h1>📊 Přehled dne</h1>
        <p>{today_cet.strftime("%-d. %-m. %Y")} · čas CET: {cet_now().strftime("%H:%M")}</p>
    </div>
    <div class="content-pad">""", unsafe_allow_html=True)

    # ── Rychlé akce (příchod/odchod/pauza) ──────────────────
    _dash_user = st.session_state.user
    _dash_att  = dict(get_attendance(_dash_user["id"])) if get_attendance(_dash_user["id"]) else None
    _absences_today = get_absences_for_date()
    _my_absence = next((a for a in _absences_today if a["user_id"] == _dash_user["id"]), None)
    if not _my_absence:
        st.markdown("#### ⚡ Rychlé akce")
        _qa_cols = st.columns(4)
        if not _dash_att or not _dash_att.get("checkin_time"):
            with _qa_cols[0]:
                if st.button("▶ Příchod", use_container_width=True, type="primary"):
                    ok, msg = do_checkin(_dash_user["id"])
                    st.success(msg) if ok else st.warning(msg); st.rerun()
        elif _dash_att.get("checkin_time") and not _dash_att.get("checkout_time"):
            _dash_pauses = get_pauses(_dash_att["id"])
            _open_p = [p for p in _dash_pauses if p["end_time"] is None]
            if not _open_p:
                with _qa_cols[0]:
                    if st.button("⏹ Odchod", use_container_width=True, type="primary"):
                        ok, msg = do_checkout(_dash_user["id"])
                        st.success(msg) if ok else st.warning(msg); st.rerun()
                with _qa_cols[1]:
                    _all_pt = PAUSE_TYPES + list(PAUSE_TYPES_PAID)
                    _dp_type = st.selectbox("Typ", _all_pt, key="dash_pt", label_visibility="collapsed")
                    if st.button("⏸ Pauza", use_container_width=True):
                        ok, msg = open_pause(_dash_att["id"], _dp_type, paid=_dp_type in PAUSE_TYPES_PAID)
                        st.success(msg) if ok else st.warning(msg); st.rerun()
                with _qa_cols[2]:
                    _doc_t = st.time_input("Odešel/a k lékaři v", value=time(9, 0),
                                           key="dash_doc_from", label_visibility="collapsed")
                    if st.button("🏥 Přišel/a z lékaře", use_container_width=True):
                        _ds = cet_today().isoformat() + " " + _doc_t.strftime("%H:%M:%S")
                        _de = now_str()
                        with get_conn() as _dcc:
                            _dcc.execute(
                                "INSERT INTO pauses(attendance_id,pause_type,start_time,end_time,paid)"
                                " VALUES(?,?,?,?,1)",
                                (_dash_att["id"], "🏥 Lékař (placená pauza)", _ds, _de)
                            )
                            _dcc.commit()
                        st.success(f"Lékař: {_doc_t.strftime('%H:%M')} – {_de[11:16]} 💚"); st.rerun()
            else:
                with _qa_cols[0]:
                    if st.button("▶ Ukončit pauzu", use_container_width=True, type="primary"):
                        ok, msg = end_pause(_dash_att["id"])
                        st.success(msg) if ok else st.warning(msg); st.rerun()
        elif _dash_att and _dash_att.get("checkout_time"):
            with _qa_cols[0]:
                if st.button("▶ 2. Příchod", use_container_width=True, type="primary"):
                    ok, msg = do_checkin(_dash_user["id"])
                    st.success(msg) if ok else st.warning(msg); st.rerun()
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    overview = get_status_overview()
    working  = [u for u in overview if u["status"] == "working"]
    paused   = [u for u in overview if u["status"] == "pause"]
    sick     = [u for u in overview if u["status"] == "sickday"]
    vacation = [u for u in overview if u["status"] == "vacation"]
    done     = [u for u in overview if u["status"] == "done"]
    offline  = [u for u in overview if u["status"] == "offline"]
    missing  = get_missing_today() if st.session_state.user["role"] == "admin" else []

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

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    def render_group(title, users, show_checkin=False):
        if not users:
            return
        st.markdown(f'<div style="font-size:.6875rem;font-weight:700;color:var(--text-muted);letter-spacing:.06em;text-transform:uppercase;margin:14px 0 8px">{title}</div>', unsafe_allow_html=True)
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
    if missing:
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        st.markdown(
            f'<div style="background:#fff7ed;border-left:4px solid #f59e0b;border-radius:8px;'
            f'padding:10px 14px;margin-bottom:8px">'
            f'<strong style="color:#92400e">⚠️ Chybí v systému dnes ({len(missing)} osob):</strong>'
            f'</div>', unsafe_allow_html=True
        )
        for _mu in missing:
            st.markdown(f"""
            <div class="person-row">
                {avatar_html(_mu['display_name'], _mu['color'])}
                <div style="flex:1"><div class="name">{_mu['display_name']}</div>
                <div class="detail">Bez příchodu ani absence</div></div>
                <span class="badge badge-offline">❓ Chybí</span>
            </div>""", unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# PAGE: MY ATTENDANCE
# ─────────────────────────────────────────────
def page_my_attendance():
    user = st.session_state.user
    today_cet = cet_today()
    st.markdown(f"""<div class="page-header">
        <h1>🕐 Moje docházka</h1>
        <p>Dnes: {today_cet.strftime("%-d. %-m. %Y")} · {cet_now().strftime("%H:%M")} CET</p>
    </div>
    <div class="content-pad">""", unsafe_allow_html=True)

    absences_today = get_absences_for_date()
    my_absence = next((a for a in absences_today if a["user_id"] == user["id"]), None)
    if my_absence:
        label = {"vacation": "Dovolená", "nemoc": "Nemoc / PN"}.get(my_absence["absence_type"], "Sickday")
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
                all_pause_types = PAUSE_TYPES + list(PAUSE_TYPES_PAID)
                pause_type = st.selectbox("Typ pauzy", all_pause_types, label_visibility="collapsed")
                is_paid_pause = pause_type in PAUSE_TYPES_PAID
                if st.button("⏸ Zahájit pauzu", use_container_width=True):
                    ok, msg = open_pause(att["id"], pause_type, paid=is_paid_pause)
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
                paid_tag = " 💚 placená" if p.get("paid") else ""
                st.markdown(f"- **{p['pause_type']}**: {p['start_time'][:5]} – {end}{dur}{paid_tag}")

    # Email
    with st.expander("E-mail pro notifikace"):
        _cur_email = st.session_state.user.get("email") or ""
        _new_email = st.text_input("E-mailova adresa", value=_cur_email,
                                   placeholder="jan.novak@firma.cz", key="my_email_input")
        if st.button("Ulozit e-mail", key="save_my_email"):
            update_user_email(user["id"], _new_email)
            st.session_state.user["email"] = _new_email.strip()
            st.success("E-mail ulozen")
            st.rerun()
        st.caption("Na tento e-mail prijde potvrzeni o schvaleni absence.")

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
    is_brigardnik = user.get("role") == "brigádník"
    workdays_so_far = count_workdays_so_far(year, month)
    absence_days    = count_absence_workdays(user["id"], year, month)
    eff_days        = effective_workdays(user["id"], year, month)
    expected_sec    = 0 if is_brigardnik else eff_days * 8 * 3600
    wd_sec  = sum(s["worked_seconds"] for s in stats if not s["is_weekend"])
    we_sec  = sum(s["worked_seconds"] for s in stats if s["is_weekend"])
    diff    = wd_sec - expected_sec

    fund_summ = leave_summary(user["id"], year)
    vr = fund_summ["vacation_remain"]
    sr = fund_summ["sickday_remain"]
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class="card card-blue"><h3>Celkem odpracováno</h3>
            <div class="value" style="color:#1a3a5c">{seconds_to_hm(wd_sec + we_sec)}</div>
            <div class="sub">vč. {seconds_to_hm(we_sec)} víkend</div></div>""", unsafe_allow_html=True)
    with c2:
        if is_brigardnik:
            st.markdown(f"""<div class="card card-gray"><h3>Brigádník – bez fondu</h3>
                <div class="value" style="color:#3a5068">{seconds_to_hm(wd_sec)}</div>
                <div class="sub">Celkem odpracováno tento měsíc</div></div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""<div class="card card-gray"><h3>Fond pracovní doby</h3>
                <div class="value" style="color:#3a5068">{seconds_to_hm(expected_sec)}</div>
                <div class="sub">{eff_days:.1f} dní (−{absence_days:.1f} absence)</div></div>""", unsafe_allow_html=True)
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

    vc2 = "green" if vr > 3 else "yellow" if vr > 0 else "red"
    sc2 = "green" if sr > 1 else "yellow" if sr > 0 else "red"
    f1, f2 = st.columns(2)
    with f1:
        st.markdown(f"""<div class="card card-{vc2}"><h3>🏖 Dovolená {year}</h3>
            <div class="value" style="font-size:1.5rem">{vr:.1f} dní</div>
            <div class="sub">zbývá z {fund_summ['vacation_total']} dní</div></div>""", unsafe_allow_html=True)
    with f2:
        st.markdown(f"""<div class="card card-{sc2}"><h3>🤒 Sickday {year}</h3>
            <div class="value" style="font-size:1.5rem">{sr} dní</div>
            <div class="sub">zbývá z {fund_summ['sickday_total']} dní</div></div>""", unsafe_allow_html=True)

    if stats:
        df = pd.DataFrame(stats)
        df["Odpracováno"] = df["worked_seconds"].apply(seconds_to_hm)
        df["Typ"]         = df["is_weekend"].apply(lambda x: "🏖 Víkend" if x else "📋 Pracovní")
        df = df[["date","checkin","checkout","Odpracováno","Typ"]].rename(
            columns={"date":"Datum","checkin":"Příchod","checkout":"Odchod"})
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# PAGE: ABSENCES
# ─────────────────────────────────────────────
def page_absences():
    user = st.session_state.user
    yr   = cet_today().year
    summ = leave_summary(user["id"], yr)
    st.markdown("""<div class="page-header">
        <h1>🏖 Absence</h1>
        <p>Nahlášení dovolené, sickday nebo nemoci – čeká na schválení administrátora</p>
    </div>
    <div class="content-pad">""", unsafe_allow_html=True)

    # ── Přehled fondů ──────────────────────────────────────────
    vac_rem  = summ["vacation_remain"]
    sick_rem = summ["sickday_remain"]
    vac_color  = "green" if vac_rem  > 3  else "yellow" if vac_rem  > 0 else "red"
    sick_color = "green" if sick_rem > 1  else "yellow" if sick_rem > 0 else "red"
    carry_str  = f" (+{summ['vacation_carry']} převod)" if summ["vacation_carry"] else ""
    st.markdown(f"""
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px">
      <div class="card card-{vac_color}">
        <h3>🏖 Fond dovolené {yr}</h3>
        <div class="value" style="font-size:1.5rem">{vac_rem:.1f} dní</div>
        <div class="sub">z {summ['vacation_total']} dní (základ {summ['vacation_base']}{carry_str}) · čerpáno {summ['vacation_used']:.1f}</div>
      </div>
      <div class="card card-{sick_color}">
        <h3>🤒 Fond sickday {yr}</h3>
        <div class="value" style="font-size:1.5rem">{sick_rem} dní</div>
        <div class="sub">z {summ['sickday_total']} dní · čerpáno {summ['sickday_used']}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["➕ Nová žádost", "🏁 Konec nemoci", "📋 Moje absence"])

    # ── Tab 1: Nová žádost ──────────────────────────────────────
    with tab1:
        abs_type = st.selectbox(
            "Typ absence",
            ["vacation", "sickday", "nemoc", "lekar_den"],
            format_func=lambda x: {
                "vacation":   "🏖 Dovolená",
                "sickday":    "🤒 Sickday (1 den z fondu)",
                "nemoc":      "🏥 Nemoc / PN (více dní, nečerpá fond)",
                "lekar_den":  "🏥 Lékař – celý den (nečerpá fond, = 8 h v práci)",
            }[x]
        )

        if abs_type == "sickday":
            if summ["sickday_remain"] <= 0:
                st.warning(f"Nemáte žádný zbývající sickday (čerpáno {summ['sickday_used']}/{summ['sickday_total']}).")
            sick_date = st.date_input("Den", value=cet_today(),
                                      min_value=cet_today() - timedelta(days=60), format="DD.MM.YYYY")
            date_from = date_to = sick_date
            half_days_sel = []

        elif abs_type == "nemoc":
            st.caption("Zadejte začátek nemoci. Konec lze doplnit v záložce 'Konec nemoci'. Nemoc nečerpá fond.")
            date_from = st.date_input("Začátek nemoci", value=cet_today(),
                                      min_value=cet_today() - timedelta(days=90), format="DD.MM.YYYY")
            date_to = date_from
            half_days_sel = []

        elif abs_type == "lekar_den":
            st.caption(
                "Zaznamená placenou celodenní návštěvu lékaře. **Nečerpá fond dovolené ani sickday.** "
                "Docházka bude mít příchod 8:00, placenou pauzu a odchod 16:00 – odpracováno 8 h."
            )
            date_from = st.date_input("Datum návštěvy lékaře", value=cet_today(), format="DD.MM.YYYY")
            date_to = date_from
            half_days_sel = []

        else:  # vacation
            if summ["vacation_remain"] <= 0:
                st.warning(f"Nemáte žádnou zbývající dovolenou (čerpáno {summ['vacation_used']:.1f}/{summ['vacation_total']} dní).")
            c1, c2 = st.columns(2)
            with c1:
                date_from = st.date_input("Od", value=cet_today(), format="DD.MM.YYYY")
            with c2:
                date_to = st.date_input("Do", value=cet_today(), format="DD.MM.YYYY")

            half_days_sel = []
            if date_to >= date_from:
                workdays_in_range = []
                cur = date_from
                while cur <= date_to:
                    if is_workday(cur):
                        workdays_in_range.append(cur)
                    cur += timedelta(days=1)

                if workdays_in_range:
                    total_full = len(workdays_in_range)
                    st.caption(
                        f"Rozsah obsahuje **{total_full}** "
                        f"{'pracovní den' if total_full == 1 else 'pracovní dny' if total_full < 5 else 'pracovních dní'}. "
                        "Zaškrtněte dny, které chcete vzít jako **půlden** (0,5 dne z fondu)."
                    )
                    DOW_NAMES  = ["Po", "Út", "St", "Čt", "Pá", "So", "Ne"]
                    MONTH_SH   = ["led","úno","bře","dub","kvě","čer","čvc","srp","zář","říj","lis","pro"]
                    chunk_size = min(7, len(workdays_in_range))
                    for chunk_start in range(0, len(workdays_in_range), chunk_size):
                        chunk = workdays_in_range[chunk_start:chunk_start + chunk_size]
                        cols  = st.columns(len(chunk))
                        for col, wd in zip(cols, chunk):
                            label = f"{DOW_NAMES[wd.weekday()]} {wd.day}.{MONTH_SH[wd.month-1]}"
                            if col.checkbox(label, key=f"hd_{wd.isoformat()}", value=False):
                                half_days_sel.append(wd)

                    full_cnt     = len(workdays_in_range) - len(half_days_sel)
                    half_cnt     = len(half_days_sel)
                    total_deduct = full_cnt + half_cnt * 0.5
                    remain_after = summ["vacation_remain"] - total_deduct
                    color_remain = "green" if remain_after >= 0 else "red"
                    st.markdown(
                        f"**Odečteno z fondu:** {total_deduct:.1f} dní "
                        f"({full_cnt}× celý" + (f", {half_cnt}× půlden" if half_cnt else "") + ")"
                        f" &nbsp;·&nbsp; Zbývá: "
                        f"<span style='font-weight:700;color:{'#145c38' if remain_after>=0 else '#9b2116'}'>"
                        f"{remain_after:.1f} dní</span>",
                        unsafe_allow_html=True
                    )

        note = st.text_input("Poznámka (nepovinné)")

        if st.button("Odeslat žádost", type="primary"):
            if abs_type not in ("nemoc", "sickday", "lekar_den") and date_to < date_from:
                st.error("Datum 'Do' musí být stejné nebo pozdější než 'Od'.")
            elif abs_type == "lekar_den":
                # Celodenní lékař – přímo do docházky, bez fronty schválení
                _ld_iso  = date_from.isoformat()
                _ld_cin  = _ld_iso + " 08:00:00"
                _ld_cout = _ld_iso + " 16:00:00"
                with get_conn() as _ldc:
                    _ldr = _ldc.execute(
                        "SELECT id, checkin_time, checkout_time FROM attendance WHERE user_id=? AND date=?",
                        (user["id"], _ld_iso)
                    ).fetchone()
                    if _ldr:
                        _ld_att_id = _ldr["id"]
                        if not _ldr["checkin_time"]:
                            _ldc.execute("UPDATE attendance SET checkin_time=? WHERE id=?", (_ld_cin, _ld_att_id))
                        if not _ldr["checkout_time"]:
                            _ldc.execute("UPDATE attendance SET checkout_time=? WHERE id=?", (_ld_cout, _ld_att_id))
                    else:
                        _ldc_cur = _ldc.execute(
                            "INSERT INTO attendance(user_id,date,checkin_time,checkout_time) VALUES(?,?,?,?)",
                            (user["id"], _ld_iso, _ld_cin, _ld_cout)
                        )
                        _ld_att_id = _ldc_cur.lastrowid
                    _ldc.execute(
                        "INSERT INTO pauses(attendance_id,pause_type,start_time,end_time,paid)"
                        " VALUES(?,?,?,?,1)",
                        (_ld_att_id, "🏥 Lékař – celý den (placená)", _ld_cin, _ld_cout)
                    )
                    _ldc.commit()
                st.success(f"✅ Celodenní lékař zaznamenán pro {date_from.strftime('%d.%m.%Y')} – 8 h v pracovní době 💚")
                st.rerun()
            else:
                request_absence(user["id"], abs_type, date_from, date_to, note,
                                half_days=half_days_sel if abs_type == "vacation" else [])
                type_names = {"vacation":"Dovolená","sickday":"Sickday","nemoc":"Nemoc/PN"}
                st.success(f"✅ Žádost o {type_names.get(abs_type, abs_type)} odeslána "
                           f"({date_from.strftime('%d.%m.')}"
                           f"{(' – ' + date_to.strftime('%d.%m.%Y')) if date_to != date_from else ('.' + date_from.strftime('%Y'))}) "
                           f"– čeká na schválení administrátorem.")
                st.rerun()

    # ── Tab 2: Konec nemoci ─────────────────────────────────────
    with tab2:
        my_absences = get_user_absences(user["id"])
        # Otevřené nemoci = typ nemoc, approved=1, date_to == date_from (konec ještě nezadán)
        open_nemoci = [
            a for a in my_absences
            if a["absence_type"] == "nemoc" and a["approved"] == 1
            and a["date_to"] == a["date_from"]
        ]
        if not open_nemoci:
            st.info("Žádná otevřená nemoc – buď ještě nebyla schválena, nebo konec byl již zadán.")
        else:
            st.markdown(f"Máte **{len(open_nemoci)}** otevřenou nemoc:")
            for a in open_nemoci:
                st.markdown(f"""<div class="card card-red">
                    <strong style="color:#1e293b">🏥 Nemoc od {a['date_from']}</strong>
                    {f'<span style="color:#64748b"> · {a["note"]}</span>' if a.get('note') else ''}
                </div>""", unsafe_allow_html=True)
                end_key = f"end_nemoc_{a['id']}"
                end_date = st.date_input(
                    "Datum ukončení nemoci",
                    value=cet_today(),
                    min_value=date.fromisoformat(a["date_from"]),
                    key=end_key,
                    format="DD.MM.YYYY")
                if st.button("Uložit konec nemoci", key=f"btn_end_{a['id']}"):
                    update_nemoc_end(a["id"], end_date)
                    st.success(f"Konec nemoci uložen: {end_date} ✓")
                    st.rerun()
                st.markdown("---")

    # ── Tab 3: Moje absence ─────────────────────────────────────
    with tab3:
        absences = get_user_absences(user["id"])
        if not absences:
            st.info("Žádné absence.")
        type_labels = {
            "sickday":       "🤒 Sickday",
            "nemoc":         "🏥 Nemoc / PN",
            "vacation":      "🏖 Dovolená",
            "vacation_half": "🌅 Dovolená půlden",
        }
        status_map = {0: ("⏳ Čeká na schválení", "yellow"), 1: ("✅ Schváleno", "green"), -1: ("❌ Zamítnuto", "red")}
        for a in absences:
            type_label = type_labels.get(a["absence_type"], a["absence_type"])
            status_str, s_color = status_map.get(a["approved"], ("?", "gray"))
            note_str  = f" · {a['note']}" if a.get("note") else ""
            # Pro nemoc s nezadaným koncem zobrazíme "od X – konec nezadán"
            if a["absence_type"] == "nemoc" and a["date_to"] == a["date_from"]:
                date_str = f"od {a['date_from']} – <em>konec nezadán</em>"
            else:
                date_str = a["date_from"] if a["date_from"] == a["date_to"] else f"{a['date_from']} – {a['date_to']}"
            hd_list   = json.loads(a.get("half_days") or "[]")
            half_info = (" · 🌅 půlden: " + ", ".join(hd_list)) if hd_list else ""
            email_str = " · ✉ email odeslán" if a.get("email_sent") else ""
            st.markdown(f"""<div class="card card-{s_color}">
                <strong style="color:#1e293b">{type_label}</strong>
                <span style="color:#475569"> · {date_str}{note_str}{half_info}</span><br>
                <small style="color:#64748b">{status_str}{email_str}</small>
            </div>""", unsafe_allow_html=True)
            if a["approved"] == 0:
                if st.button("Zrušit žádost", key=f"del_abs_{a['id']}"):
                    delete_absence(a["id"])
                    st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# PAGE: TIME CORRECTIONS
# ─────────────────────────────────────────────
def page_corrections():
    user = st.session_state.user
    st.markdown("""<div class="page-header">
        <h1>✏️ Úpravy záznamu</h1>
        <p>Žádost o opravu příchodu, odchodu nebo pauzy – schvaluje administrátor</p>
    </div>
    <div class="content-pad">""", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["➕ Nová žádost o úpravu", "📋 Moje žádosti"])

    with tab1:
        st.markdown("Vyplňte datum a požadované časy. Administrátor žádost schválí nebo zamítne.")
        corr_date = st.date_input("Datum záznamu", value=cet_today(),
                                   min_value=cet_today() - timedelta(days=60), format="DD.MM.YYYY")

        st.markdown("**Požadované časy** \\*")
        rc1, rc2 = st.columns(2)
        with rc1:
            req_in  = st.text_input("Příchod *", placeholder="07:45", key="req_in")
            req_bs  = st.text_input("Začátek pauzy", placeholder="11:30", key="req_bs")
        with rc2:
            req_out = st.text_input("Odchod *", placeholder="15:30", key="req_out")
            req_be  = st.text_input("Konec pauzy", placeholder="12:00", key="req_be")

        reason = st.text_area("Důvod úpravy *", placeholder="Popište důvod požadované opravy záznamu…")

        if st.button("Odeslat žádost o úpravu", type="primary"):
            if not req_in or not req_out or not reason.strip():
                st.error("Vyplňte povinná pole: Příchod, odchod a důvod.")
            else:
                request_correction(
                    user["id"], corr_date.isoformat(),
                    "", "", "", "",
                    req_in, req_out, req_bs, req_be, reason
                )
                st.success("Žádost odeslána – administrátor ji brzy vyřídí ✓")
                st.rerun()

    with tab2:
        corrections = get_user_corrections(user["id"])
        if not corrections:
            st.info("Žádné žádosti o úpravu.")
        for c in corrections:
            req_str  = f"{c['req_in']} – {c['req_out']}"
            admin_note_str = f"<br><small style='color:#64748b'>Poznámka admina: {c['admin_note']}</small>" if c.get("admin_note") else ""
            st.markdown(f"""<div class="card">
                <div style="display:flex;justify-content:space-between;align-items:flex-start">
                    <div>
                        <strong style="color:#1e293b">{c['date']}</strong>
                        <span style="color:#475569"> · požadováno {req_str}</span><br>
                        <small style="color:#64748b">{c['reason']}</small>{admin_note_str}
                    </div>
                    {correction_status_badge(c['status'])}
                </div>
            </div>""", unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# PAGE: REPORTS
# ─────────────────────────────────────────────
def page_reports():
    user     = st.session_state.user
    is_admin = user["role"] == "admin"
    st.markdown("""<div class="page-header">
        <h1>📈 Výkazy docházky</h1>
        <p>Měsíční přehled odpracovaných hodin</p>
    </div>
    <div class="content-pad">""", unsafe_allow_html=True)

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
        stats     = get_month_stats(tu["id"], year, month)
        workdays  = count_workdays_so_far(year, month)
        ab_days   = count_absence_workdays(tu["id"], year, month)
        eff_days  = max(0, workdays - ab_days)
        wd_sec    = sum(s["worked_seconds"] for s in stats if not s["is_weekend"])
        we_sec    = sum(s["worked_seconds"] for s in stats if s["is_weekend"])
        expected  = eff_days * 8 * 3600
        all_rows.append({
            "Jméno": tu["display_name"],
            "Prac. dny": workdays,
            "Absence (dny)": ab_days,
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

        # XLSX – openpyxl nemusí být k dispozici (Streamlit Cloud)
        xlsx_buf = None
        try:
            import openpyxl  # noqa: F401
            xlsx_buf = io.BytesIO()
            with pd.ExcelWriter(xlsx_buf, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Přehled", index=False)
                for tu in target_users:
                    _s = get_month_stats(tu["id"], year, month)
                    if _s:
                        df2 = pd.DataFrame(_s)
                        df2["Odpracováno"] = df2["worked_seconds"].apply(seconds_to_hm)
                        df2["Typ"] = df2["is_weekend"].apply(lambda x: "Víkend" if x else "Pracovní")
                        df2 = df2[["date","checkin","checkout","Odpracováno","Typ"]].rename(
                            columns={"date":"Datum","checkin":"Příchod","checkout":"Odchod"})
                        df2.to_excel(writer, sheet_name=tu["display_name"][:31], index=False)
            xlsx_buf.seek(0)
        except ImportError:
            pass

        btn_cols = st.columns([1, 1, 4]) if xlsx_buf else st.columns([1, 5])
        with btn_cols[0]:
            st.download_button("⬇ CSV", data=csv,
                               file_name=f"dochazka_{year}_{month:02d}.csv", mime="text/csv")
        if xlsx_buf:
            with btn_cols[1]:
                st.download_button("⬇ XLSX", data=xlsx_buf,
                                   file_name=f"dochazka_{year}_{month:02d}.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            with btn_cols[1]:
                st.caption("XLSX nedostupné – přidejte `openpyxl` do requirements.txt")

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
                # Pauzy
                _rep_user = target_users[0]
                _all_pauses_rows = []
                with get_conn() as _pc:
                    _month_pauses = _pc.execute(
                        """SELECT p.*, a.date FROM pauses p
                           JOIN attendance a ON p.attendance_id=a.id
                           WHERE a.user_id=? AND strftime('%Y',a.date)=?
                           AND strftime('%m',a.date)=? ORDER BY a.date,p.start_time""",
                        (_rep_user["id"], str(year), f"{month:02d}")
                    ).fetchall()
                for _p in _month_pauses:
                    _pd = dict(_p)
                    _dur = ""
                    if _pd.get("end_time"):
                        _ds = time_to_seconds(_pd["end_time"]) - time_to_seconds(_pd["start_time"])
                        _dur = seconds_to_hm(_ds)
                    _all_pauses_rows.append({
                        "Datum": _pd["date"], "Typ": _pd["pause_type"],
                        "Začátek": _pd["start_time"][11:16] if _pd["start_time"] else "",
                        "Konec": _pd["end_time"][11:16] if _pd.get("end_time") else "—",
                        "Trvání": _dur,
                        "Placená": "💚 Ano" if _pd.get("paid") else "Ne",
                    })
                if _all_pauses_rows:
                    st.markdown("#### Pauzy v měsíci")
                    st.dataframe(pd.DataFrame(_all_pauses_rows), use_container_width=True, hide_index=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# PAGE: ADMIN
# ─────────────────────────────────────────────
def page_admin():
    st.markdown("""<div class="page-header">
        <h1>⚙️ Správa</h1>
        <p>Uživatelé, schválení absencí a úprav docházky</p>
    </div>
    <div class="content-pad">""", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
        "👥 Uživatelé", "➕ Nový uživatel",
        "🤒 Vložit nemoc", "✅ Schválení absencí", "✏️ Schválení úprav",
        "📊 Fondy dovolené", "💾 Záloha databáze", "✏️ Přímá editace docházky",
        "Editace dovolene"
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

                st.markdown("---")
                st.markdown("**E-mail pro notifikace**")
                col_em1, col_em2 = st.columns([3, 1])
                with col_em1:
                    new_email_val = st.text_input(
                        "E-mail", value=u.get("email") or "",
                        placeholder="jan.novak@firma.cz", key=f"email_{u['id']}"
                    )
                with col_em2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Ulozit", key=f"save_email_{u['id']}"):
                        update_user_email(u["id"], new_email_val)
                        st.success("E-mail ulozen")
                        st.rerun()

                # Deactivate
                if u["id"] != st.session_state.user["id"]:
                    st.markdown("---")
                    if st.button("Deaktivovat ucet", key=f"del_{u['id']}"):
                        deactivate_user(u["id"])
                        st.warning(f"Ucet @{u['username']} byl deaktivovan.")
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
                new_role     = st.selectbox("Role", ["user", "admin", "brigádník"])
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
                sick_from = st.date_input("Od", value=cet_today(), format="DD.MM.YYYY")
            with c2:
                sick_to   = st.date_input("Do", value=cet_today(), format="DD.MM.YYYY")
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

        type_labels = {"sickday": "🤒 Sickday", "nemoc": "🏥 Nemoc/PN", "vacation": "🏖 Dovolená", "vacation_half": "🌅 Půlden"}
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

    # ── Tab 6: Fondy dovolené ──────────────────────────────
    with tab6:
        today_f   = cet_today()
        yr_opts   = [today_f.year - 1, today_f.year, today_f.year + 1]
        fund_year = st.selectbox("Rok", yr_opts, index=1, key="fund_year")
        st.markdown("Upravte fond dovolené a počet sickday dní pro každého zaměstnance.")
        all_users_f = get_all_users()
        for u in all_users_f:
            fund  = ensure_leave_fund(u["id"], fund_year)
            used_v = get_used_vacation(u["id"], fund_year)
            used_s = get_used_sickdays(u["id"], fund_year)
            total_v = fund["vacation_days"] + fund["vacation_carry"]
            initials = "".join(w[0].upper() for w in u["display_name"].split()[:2])
            color = u.get("color") or "#1f5e8c"
            st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">
              <div style="width:32px;height:32px;border-radius:16px;background:{color}22;color:{color};
                border:2px solid {color}55;display:flex;align-items:center;justify-content:center;
                font-weight:800;font-size:11px">{initials}</div>
              <strong style="font-size:14px;color:#1e293b">{u['display_name']}</strong>
              <span style="font-size:12px;color:#94a3b8">
                🏖 {used_v:.1f}/{total_v} dní &nbsp;·&nbsp; 🤒 {used_s}/{fund['sickday_days']} sickday
              </span></div>""", unsafe_allow_html=True)
            with st.expander(f"Upravit fond – {u['display_name']}"):
                fc1, fc2, fc3 = st.columns(3)
                with fc1:
                    vd = st.number_input("Základní dovolená (dny)", min_value=0, max_value=60,
                                         value=fund["vacation_days"], key=f"vd_{u['id']}_{fund_year}")
                with fc2:
                    vc = st.number_input("Převod z minulého roku (dny)", min_value=0, max_value=60,
                                         value=fund["vacation_carry"], key=f"vc_{u['id']}_{fund_year}")
                with fc3:
                    sd = st.number_input("Fond sickday (dny)", min_value=0, max_value=30,
                                         value=fund["sickday_days"], key=f"sd_{u['id']}_{fund_year}")
                st.caption(f"Celkový fond dovolené: {int(vd)+int(vc)} dní · zbývá: {total_v - used_v:.1f} dní")
                if st.button("💾 Uložit fond", key=f"save_fund_{u['id']}_{fund_year}"):
                    update_leave_fund(u["id"], fund_year, int(vd), int(vc), int(sd))
                    st.success(f"Uloženo: {u['display_name']} – dovolená {int(vd)}+{int(vc)} dní, sickday {int(sd)} ✓")
                    st.rerun()


    # ── Tab 7: Záloha / Export / Import ─────────────────────
    with tab7:
        st.markdown("### 💾 Záloha a obnova databáze")

        # Info o persistenci
        st.info(
            "**Kde zálohy žijí?** Automatické zálohy se ukládají do složky `backups/` "
            "vedle databáze. Na **vlastním serveru** (VPS, Railway s volumes, Docker) zálohy "
            "přežijí restart aplikace. Na **Streamlit Cloud** je filesystem ephemeral – "
            "zálohy se smažou při redeploymentu. V takovém případě používejte ruční stažení zálohy "
            "a ukládejte ji mimo cloud.",
            icon="ℹ️"
        )

        # ── Automatická záloha – stav ──────────────────────────
        st.markdown("#### 🔄 Automatická záloha")
        _bkp_interval = st.number_input(
            "Interval automatické zálohy (hodiny)", min_value=1, max_value=168,
            value=BACKUP_INTERVAL_H, key="bkp_interval_display", disabled=True
        )
        _bcol1, _bcol2 = st.columns(2)
        with _bcol1:
            if st.button("▶ Zálohovat nyní", use_container_width=True):
                _bp = _do_backup("manual")
                if _bp:
                    st.success(f"✅ Záloha vytvořena: `{Path(_bp).name}`")
                else:
                    st.error("Záloha se nezdařila.")
        with _bcol2:
            _bkp_running = _BACKUP_STARTED
            st.markdown(
                f"<div style='padding:8px 12px;border-radius:8px;font-size:13px;"
                f"background:{'#dcfce7' if _bkp_running else '#fee2e2'};"
                f"color:{'#14532d' if _bkp_running else '#7f1d1d'};font-weight:600'>"
                f"{'🟢 Automatická záloha běží' if _bkp_running else '🔴 Automatická záloha neběží'}</div>",
                unsafe_allow_html=True
            )

        # ── Přehled existujících záloh ─────────────────────────
        _backups = list_backups()
        if _backups:
            st.markdown(f"**Uložené zálohy** ({len(_backups)} souborů ve složce `backups/`):")
            for _b in _backups[:10]:
                _sz = f"{_b['size']/1024:.1f} kB"
                _lbl_color = "#dbeafe" if _b["label"] == "auto" else "#dcfce7"
                _lbl_text  = "auto" if _b["label"] == "auto" else "manuální"
                _bcols = st.columns([3, 1, 1])
                _bcols[0].markdown(
                    f"<span style='font-size:12px;font-family:monospace'>{_b['name']}</span> "
                    f"<span style='background:{_lbl_color};border-radius:4px;padding:1px 6px;"
                    f"font-size:11px;font-weight:600'>{_lbl_text}</span> "
                    f"<span style='color:#94a3b8;font-size:11px'>{_sz}</span>",
                    unsafe_allow_html=True
                )
                with open(_b["path"], "rb") as _bf:
                    _bdata = _bf.read()
                _bcols[1].download_button(
                    "⬇", data=_bdata, file_name=_b["name"],
                    mime="application/octet-stream", key=f"dl_{_b['name']}"
                )
        else:
            st.caption("Zatím žádné zálohy. Klikněte na '▶ Zálohovat nyní'.")

        st.markdown("---")

        # ── Ruční stažení a export ─────────────────────────────
        _ecol1, _ecol2 = st.columns(2)
        with _ecol1:
            st.markdown("#### ⬇ Záloha SQLite")
            if DB_PATH.exists():
                with open(DB_PATH, "rb") as _fdb:
                    _db_bytes = _fdb.read()
                _ts = datetime.now().strftime("%Y%m%d_%H%M")
                st.download_button(
                    "⬇ Stáhnout aktuální DB (.sqlite)",
                    data=_db_bytes,
                    file_name=f"dochazka_backup_{_ts}.sqlite",
                    mime="application/octet-stream",
                    use_container_width=True,
                )
                st.caption(f"{len(_db_bytes)/1024:.1f} kB")

        with _ecol2:
            st.markdown("#### ⬇ Export JSON")
            if DB_PATH.exists():
                with get_conn() as _ec:
                    _tables = [r[0] for r in _ec.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()]
                    _export = {t: [dict(r) for r in _ec.execute(f"SELECT * FROM {t}").fetchall()]
                               for t in _tables}
                _json_bytes = json.dumps(_export, ensure_ascii=False, indent=2).encode("utf-8")
                _ts2 = datetime.now().strftime("%Y%m%d_%H%M")
                st.download_button(
                    "⬇ Exportovat jako JSON",
                    data=_json_bytes,
                    file_name=f"dochazka_export_{_ts2}.json",
                    mime="application/json",
                    use_container_width=True,
                )
                st.caption(f"Tabulky: {', '.join(_tables)}")

        st.markdown("---")
        st.markdown("#### ⬆ Obnova ze zálohy")
        st.warning("⚠️ **Obnova přepíše celou stávající databázi!** Nejdřív si stáhněte aktuální zálohu.")
        _uploaded = st.file_uploader(
            "Nahrajte záložní soubor (.sqlite / .db)",
            type=["sqlite", "db", "sqlite3"],
            key="db_restore_upload"
        )
        if _uploaded is not None:
            _confirm = st.checkbox("Rozumím – obnova přepíše stávající data", key="confirm_restore")
            if st.button("🔄 Obnovit databázi", type="primary", disabled=not _confirm):
                _data = _uploaded.read()
                if _data[:16] == b"SQLite format 3\x00":
                    # Záloha před obnovením
                    _do_backup("pre_restore")
                    with open(DB_PATH, "wb") as _fout:
                        _fout.write(_data)
                    st.success("✅ Databáze obnovena (automatická záloha před obnovením byla uložena). Odhlaste se a přihlaste znovu.")
                else:
                    st.error("❌ Soubor není platná SQLite databáze.")

        st.markdown("---")
        st.markdown("#### 📊 Statistiky databáze")
        if DB_PATH.exists():
            with get_conn() as _sc:
                _stat_cols = st.columns(5)
                for _ci, (_tbl, _lbl) in enumerate([
                    ("users","Uživatelé"), ("attendance","Záznamy"),
                    ("absences","Absence"), ("time_corrections","Žádosti"),
                    ("leave_funds","Fondy")
                ]):
                    try:
                        _stat_cols[_ci].metric(_lbl, _sc.execute(f"SELECT COUNT(*) FROM {_tbl}").fetchone()[0])
                    except Exception:
                        pass

    # ── Tab 8: Přímá editace docházky ───────────────────────
    with tab8:
        st.markdown("### ✏️ Přímá editace docházky")
        st.caption("Administrátor může přímo upravit nebo vytvořit záznam docházky bez žádosti zaměstnance.")

        _eu = get_all_users()
        _eu_map = {u["id"]: u["display_name"] for u in _eu}
        _sel_uid = st.selectbox(
            "Zaměstnanec", [u["id"] for u in _eu],
            format_func=lambda x: _eu_map[x], key="edit_att_uid"
        )
        _sel_day = st.date_input(
            "Datum", value=cet_today(), key="edit_att_day", format="DD.MM.YYYY"
        )

        # Načti existující záznam
        _att = get_attendance(_sel_uid, _sel_day.isoformat())
        _att_dict = dict(_att) if _att else {}
        _pauses   = get_pauses(_att["id"]) if _att else []

        # Zobraz stávající data
        if _att_dict:
            st.markdown(
                f"<div style='background:#f0f9ff;border-left:4px solid #1d4ed8;border-radius:8px;"
                f"padding:10px 14px;margin-bottom:12px;font-size:13px'>"
                f"📋 Stávající záznam: příchod <strong>{_att_dict.get('checkin_time','—')}</strong>"
                f", odchod <strong>{_att_dict.get('checkout_time','—')}</strong>"
                + (f", {len(_pauses)} pauza/pauz" if _pauses else "")
                + "</div>",
                unsafe_allow_html=True
            )
        else:
            st.caption("Pro tento den neexistuje žádný záznam – vyplněním formuláře ho vytvoříte.")

        # ── Formulář příchod / odchod ──────────────────────────
        st.markdown("**Příchod a odchod**")
        _fc1, _fc2 = st.columns(2)
        with _fc1:
            _new_in  = st.text_input("Příchod (HH:MM)", value=_att_dict.get("checkin_time", "") or "",
                                     placeholder="07:30", key="edit_att_in")
        with _fc2:
            _new_out = st.text_input("Odchod (HH:MM)", value=_att_dict.get("checkout_time", "") or "",
                                     placeholder="16:00", key="edit_att_out")

        _edit_note = st.text_input("Poznámka k úpravě (interní)", key="edit_att_note", placeholder="Oprava záznamu, zapomenutý příchod…")

        def _valid_time(t):
            if not t: return True
            import re as _re
            return bool(_re.match(r"^\d{1,2}:\d{2}$", t.strip()))

        _save_ok = _valid_time(_new_in) and _valid_time(_new_out)
        if not _save_ok:
            st.error("Čas musí být ve formátu HH:MM (např. 07:30).")

        if st.button("💾 Uložit příchod/odchod", type="primary", disabled=not _save_ok, key="save_edit_att"):
            _cin  = (_sel_day.isoformat() + " " + _new_in.strip())  if _new_in.strip()  else None
            _cout = (_sel_day.isoformat() + " " + _new_out.strip()) if _new_out.strip() else None
            admin_set_attendance(_sel_uid, _sel_day.isoformat(), _cin, _cout)
            st.success(f"✅ Záznam pro {_eu_map[_sel_uid]} dne {_sel_day.strftime('%d.%m.%Y')} uložen.")
            st.rerun()

        # ── Správa pauz ────────────────────────────────────────
        if _att:
            st.markdown("---")
            st.markdown("**Pauzy**")
            if _pauses:
                for _p in _pauses:
                    _pcols = st.columns([2, 2, 2, 1])
                    _pcols[0].markdown(f"<small style='color:#64748b'>{_p['pause_type']}</small>", unsafe_allow_html=True)
                    _pcols[1].markdown(f"<small>začátek: <strong>{_p['start_time']}</strong></small>", unsafe_allow_html=True)
                    _pcols[2].markdown(f"<small>konec: <strong>{_p.get('end_time') or '—'}</strong></small>", unsafe_allow_html=True)
                    if _pcols[3].button("🗑", key=f"del_p_{_p['id']}", help="Smazat pauzu"):
                        admin_delete_pause(_p["id"])
                        st.rerun()
            else:
                st.caption("Žádné pauzy.")

            # Editace existující pauzy
            if _pauses:
                with st.expander("✏️ Upravit existující pauzu"):
                    _ep_sel = st.selectbox(
                        "Vyberte pauzu",
                        [p["id"] for p in _pauses],
                        format_func=lambda pid: next(
                            f"{p['pause_type']} {p['start_time'][11:16]}–{p.get('end_time','?')[11:16] if p.get('end_time') else '?'}" 
                            for p in _pauses if p["id"] == pid
                        ),
                        key="edit_pause_sel"
                    )
                    _ep = next(p for p in _pauses if p["id"] == _ep_sel)
                    _ep1, _ep2, _ep3 = st.columns(3)
                    with _ep1:
                        _ep_type = st.text_input("Typ", value=_ep["pause_type"], key="ep_type")
                    with _ep2:
                        _ep_s = st.text_input("Začátek (HH:MM)", value=_ep["start_time"][11:16], key="ep_start")
                    with _ep3:
                        _ep_e = st.text_input("Konec (HH:MM)", value=_ep["end_time"][11:16] if _ep.get("end_time") else "", key="ep_end")
                    _ep_paid = st.checkbox("Placená pauza (lékař)", value=bool(_ep.get("paid")), key="ep_paid")
                    if st.button("💾 Uložit pauzu", key="save_ep_btn"):
                        _ep_sdt = _sel_day.isoformat() + " " + _ep_s.strip() + ":00" if _ep_s.strip() else None
                        _ep_edt = _sel_day.isoformat() + " " + _ep_e.strip() + ":00" if _ep_e.strip() else None
                        with get_conn() as _epc:
                            _epc.execute(
                                "UPDATE pauses SET pause_type=?,start_time=?,end_time=?,paid=? WHERE id=?",
                                (_ep_type, _ep_sdt, _ep_edt, 1 if _ep_paid else 0, _ep_sel)
                            )
                            _epc.commit()
                        st.success("Pauza uložena ✓"); st.rerun()

            # Přidat novou pauzu
            with st.expander("➕ Přidat pauzu"):
                _pp1, _pp2, _pp3 = st.columns(3)
                with _pp1:
                    _p_type = st.selectbox("Typ", ["oběd", "přestávka", "jiné"], key="new_pause_type")
                with _pp2:
                    _p_start = st.text_input("Začátek (HH:MM)", placeholder="12:00", key="new_pause_start")
                with _pp3:
                    _p_end   = st.text_input("Konec (HH:MM)", placeholder="12:30", key="new_pause_end")
                if st.button("Přidat pauzu", key="add_pause_btn"):
                    if _valid_time(_p_start) and _p_start.strip():
                        _ps = _sel_day.isoformat() + " " + _p_start.strip()
                        _pe = (_sel_day.isoformat() + " " + _p_end.strip()) if _p_end.strip() else None
                        admin_set_pause(_att["id"], _p_type, _ps, _pe)
                        st.success("Pauza přidána ✓")
                        st.rerun()
                    else:
                        st.error("Zadejte platný čas začátku.")

        # ── Smazání celého záznamu ─────────────────────────────
        if _att:
            st.markdown("---")
            with st.expander("⚠️ Smazat celý záznam"):
                st.warning(f"Smaže příchod, odchod i všechny pauzy pro {_eu_map[_sel_uid]} dne {_sel_day.strftime('%d.%m.%Y')}.")
                if st.button("🗑 Smazat záznam", type="primary", key="del_att_btn"):
                    admin_clear_attendance(_sel_uid, _sel_day.isoformat())
                    st.success("Záznam smazán.")
                    st.rerun()


    # Tab 9: Prima editace dovolene
    with tab9:
        st.markdown("### Priama editace dovolene")
        st.caption("Administrator muze pridat nebo smazat dovolenou bez zadosti zamestnance. Zaznamy jsou automaticky schvaleny.")

        _vac_users = get_all_users()
        _vac_uid = st.selectbox(
            "Zamestnanec", [u["id"] for u in _vac_users],
            format_func=lambda x: next(u["display_name"] for u in _vac_users if u["id"] == x),
            key="vac_edit_uid"
        )
        _vac_yr = int(st.number_input("Rok", min_value=2020, max_value=2030,
                                value=cet_today().year, step=1, key="vac_edit_yr"))

        _vac_summ = leave_summary(_vac_uid, _vac_yr)
        _vac_c1, _vac_c2 = st.columns(2)
        with _vac_c1:
            _vr = _vac_summ["vacation_remain"]
            _vc = "green" if _vr > 3 else "yellow" if _vr > 0 else "red"
            st.markdown(
                f'<div class="card card-{_vc}"><h3>Dovolena {_vac_yr}</h3>'
                f'<div class="value">{_vac_summ["vacation_used"]:.1f} / {_vac_summ["vacation_total"]} dni cerpano</div>'
                f'<div class="sub">Zbyvaji {_vr:.1f} dni</div></div>',
                unsafe_allow_html=True)
        with _vac_c2:
            _sr2 = _vac_summ["sickday_remain"]
            _sc2 = "green" if _sr2 > 1 else "yellow" if _sr2 > 0 else "red"
            st.markdown(
                f'<div class="card card-{_sc2}"><h3>Sickday {_vac_yr}</h3>'
                f'<div class="value">{_vac_summ["sickday_used"]} / {_vac_summ["sickday_total"]} dni cerpano</div>'
                f'<div class="sub">Zbyvaji {_sr2} dni</div></div>',
                unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("#### Pridat absenci")

        _vadd_type = st.selectbox(
            "Typ", ["vacation", "sickday"],
            format_func=lambda x: "Dovolena" if x == "vacation" else "Sickday",
            key="vac_add_type"
        )
        _vadd_c1, _vadd_c2 = st.columns(2)
        with _vadd_c1:
            _vac_from = st.date_input("Od", value=cet_today(), format="DD.MM.YYYY", key="vac_add_from")
        with _vadd_c2:
            _vac_to = st.date_input("Do", value=cet_today(), format="DD.MM.YYYY", key="vac_add_to")

        _vac_half_sel = []
        if _vadd_type == "vacation" and _vac_to >= _vac_from:
            _vwdays = []
            _vc3 = _vac_from
            while _vc3 <= _vac_to:
                if is_workday(_vc3):
                    _vwdays.append(_vc3)
                _vc3 += timedelta(days=1)
            if _vwdays:
                st.caption("Zaskrtnete dny jako pulden (0.5 dne):")
                _DOW = ["Po", "Ut", "St", "Ct", "Pa", "So", "Ne"]
                _MSH = ["led","uno","bre","dub","kve","cer","cvc","srp","zar","rij","lis","pro"]
                _chs = min(7, len(_vwdays))
                for _ci2 in range(0, len(_vwdays), _chs):
                    _ch2 = _vwdays[_ci2:_ci2 + _chs]
                    _cc2 = st.columns(len(_ch2))
                    for _col2, _wd2 in zip(_cc2, _ch2):
                        if _col2.checkbox(
                            f"{_DOW[_wd2.weekday()]} {_wd2.day}.{_MSH[_wd2.month-1]}",
                            key=f"vadm_hd_{_wd2.isoformat()}"
                        ):
                            _vac_half_sel.append(_wd2)
                _vfc2 = len(_vwdays) - len(_vac_half_sel)
                _vhc2 = len(_vac_half_sel)
                _vded2 = _vfc2 + _vhc2 * 0.5
                _vrem2 = _vac_summ["vacation_remain"] - _vded2
                st.markdown(
                    f"Odecteno: **{_vded2:.1f} dni** &nbsp;|&nbsp; Zbyde: **{_vrem2:.1f} dni**"
                )

        _vac_note = st.text_input("Poznamka (interni)", key="vac_add_note",
                                   placeholder="Pridano administratorem")

        if st.button("Pridat absenci", type="primary", key="vac_add_btn"):
            if _vac_to < _vac_from:
                st.error("Datum Do musi byt >= Od.")
            else:
                _hd_json2 = json.dumps([d.isoformat() for d in _vac_half_sel])
                with get_conn() as _vconn:
                    _vconn.execute(
                        "INSERT INTO absences(user_id,absence_type,date_from,date_to,note,approved,half_days)"
                        " VALUES(?,?,?,?,?,1,?)",
                        (_vac_uid, _vadd_type, _vac_from.isoformat(), _vac_to.isoformat(),
                         _vac_note or "Pridano administratorem", _hd_json2)
                    )
                    _vconn.commit()
                st.success("Absence pridana a automaticky schvalena.")
                st.rerun()

        st.markdown("---")
        st.markdown("#### Existujici zaznamy")

        with get_conn() as _vconn2:
            _vac_recs = [dict(r) for r in _vconn2.execute(
                "SELECT * FROM absences WHERE user_id=? AND absence_type IN ('vacation','sickday','vacation_half')"
                " AND strftime('%Y',date_from)=? ORDER BY date_from DESC",
                (_vac_uid, str(_vac_yr))
            ).fetchall()]

        if not _vac_recs:
            st.caption("Zadne zaznamy.")
        else:
            _type_lbl2 = {"vacation": "Dovolena", "sickday": "Sickday", "vacation_half": "Pulden"}
            _stat_lbl2 = {0: "ceka", 1: "schvaleno", -1: "zamitnuto"}
            for _vr3 in _vac_recs:
                _ds2 = _vr3["date_from"] if _vr3["date_from"] == _vr3["date_to"] else f"{_vr3['date_from']} - {_vr3['date_to']}"
                _hd2 = json.loads(_vr3.get("half_days") or "[]")
                _hd_str2 = f" | puldny: {', '.join(_hd2)}" if _hd2 else ""
                _note_s2 = f" | {_vr3['note']}" if _vr3.get("note") else ""
                _rc1, _rc2 = st.columns([5, 1])
                _rc1.markdown(
                    f"**{_type_lbl2.get(_vr3['absence_type'], _vr3['absence_type'])}** "
                    f"{_ds2}{_note_s2}{_hd_str2} "
                    f"<small style='color:#94a3b8'>({_stat_lbl2.get(_vr3['approved'], '?')})</small>",
                    unsafe_allow_html=True
                )
                if _rc2.button("Smazat", key=f"del_vac_{_vr3['id']}"):
                    with get_conn() as _vconn3:
                        _vconn3.execute("DELETE FROM absences WHERE id=?", (_vr3["id"],))
                        _vconn3.commit()
                    st.success("Zaznam smazan.")
                    st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# PAGE: CALENDAR
# ─────────────────────────────────────────────
def page_calendar():
    today = cet_today()
    st.markdown("""<div class="page-header">
        <h1>📅 Kalendář absencí</h1>
        <p>Přehled dovolených, sickday a nemocí všech zaměstnanců</p>
    </div>
    <div class="content-pad">""", unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1])
    with c1:
        month = st.selectbox("Měsíc", list(range(1, 13)), index=today.month - 1,
                             format_func=lambda m: MONTH_NAMES[m-1], key="cal_month")
    with c2:
        year = st.selectbox("Rok", list(range(today.year - 1, today.year + 2)),
                            index=1, key="cal_year")

    first    = date(year, month, 1)
    last     = (date(year, month + 1, 1) - timedelta(days=1)) if month < 12 else date(year, 12, 31)
    num_days = last.day
    holidays = czech_holidays(year)

    absences  = get_all_absences_for_calendar(year, month)
    users     = get_all_users()

    # {user_id: {day: absence_type}}
    user_days = {}
    for a in absences:
        uid = a["user_id"]
        if uid not in user_days:
            user_days[uid] = {}
        ab_from = max(date.fromisoformat(a["date_from"]), first)
        ab_to   = min(date.fromisoformat(a["date_to"]),   last)
        cur = ab_from
        while cur <= ab_to:
            user_days[uid][cur.day] = a["absence_type"]
            cur += timedelta(days=1)

    TYPE_STYLE = {
        "vacation":      ("#dbeafe", "#1d4ed8", "D"),
        "vacation_half": ("#bfdbfe", "#1d4ed8", "½"),
        "sickday":       ("#fee2e2", "#991b1b", "S"),
        "nemoc":         ("#ffe4e6", "#9f1239", "N"),
    }
    DOW_CZ = ["Po", "Út", "St", "Čt", "Pá", "So", "Ne"]

    # ── Legenda ────────────────────────────────────────────────
    legend_items = [
        ("#dbeafe", "#1d4ed8", "D",         "Dovolená"),
        ("#bfdbfe", "#1d4ed8", "½",    "Dovolená půlden"),
        ("#fee2e2", "#991b1b", "S",         "Sickday"),
        ("#ffe4e6", "#9f1239", "N",         "Nemoc / PN"),
        ("#fef9c3", "#92400e", "★",    "Státní svátek"),
    ]
    leg_parts = ['<div style="display:flex;gap:14px;margin-bottom:20px;flex-wrap:wrap">']
    for bg, fg, letter, label in legend_items:
        leg_parts.append(
            '<div style="display:flex;align-items:center;gap:6px;font-size:12px;color:#475569">'
            '<div style="width:22px;height:22px;border-radius:4px;'
            + f'background:{bg};border:1px solid {fg}88;'
            + 'display:flex;align-items:center;justify-content:center;'
            + f'font-size:11px;font-weight:800;color:{fg}">{letter}</div>'
            + f'{label}</div>'
        )
    leg_parts.append('</div>')
    st.markdown("".join(leg_parts), unsafe_allow_html=True)

    # ── Tabulka ─────────────────────────────────────────────────
    # Rozměry
    DAY_W  = 44   # px – šířka buňky dne
    NAME_W = 100  # px – šířka sloupce se jménem
    ROW_H  = 40   # px – výška řádku

    rows = []

    # Záhlaví – jmenovka + dny
    hdr_cells = []
    hdr_cells.append(
        f'<th style="min-width:{NAME_W}px;width:{NAME_W}px;max-width:{NAME_W}px;'
        f'padding:8px 8px;text-align:left;font-size:10px;color:#94a3b8;font-weight:700;'
        f'white-space:nowrap;background:#f0f4f8;border-right:2px solid #cbd5e1;'
        f'border-bottom:2px solid #cbd5e1"></th>'
    )
    for dn in range(1, num_days + 1):
        d       = date(year, month, dn)
        is_wknd = d.weekday() >= 5
        is_hol  = d in holidays
        is_tod  = d == today
        if is_tod:
            hbg = "#1d4ed8"; dnc = "rgba(255,255,255,.7)"; nnc = "#fff"; nfw = "800"
        elif is_hol:
            hbg = "#fef3c7"; dnc = "#92400e"; nnc = "#92400e"; nfw = "700"
        elif is_wknd:
            hbg = "#e2e8f0"; dnc = "#94a3b8"; nnc = "#94a3b8"; nfw = "600"
        else:
            hbg = "#f0f4f8"; dnc = "#94a3b8"; nnc = "#1e293b"; nfw = "700"
        hdr_cells.append(
            f'<th style="min-width:{DAY_W}px;width:{DAY_W}px;max-width:{DAY_W}px;'
            f'text-align:center;padding:5px 1px;background:{hbg};border-bottom:2px solid #cbd5e1;">'
            f'<div style="font-size:9px;color:{dnc};font-weight:600;line-height:1.2">{DOW_CZ[d.weekday()]}</div>'
            f'<div style="font-size:15px;font-weight:{nfw};color:{nnc};line-height:1.2">{dn}</div>'
            f'</th>'
        )
    rows.append('<tr>' + "".join(hdr_cells) + '</tr>')

    # Řádky uživatelů
    for idx, u in enumerate(users):
        uid       = u["id"]
        udays     = user_days.get(uid, {})
        rbg       = "#ffffff" if idx % 2 == 0 else "#f8fafc"
        color     = u.get("color") or "#1f5e8c"
        initials  = "".join(w[0].upper() for w in u["display_name"].split()[:2])
        last_name = u["display_name"].split()[-1]
        full_name = u["display_name"]

        cells = []
        # Jmenovka – avatar + příjmení
        cells.append(
            f'<td style="min-width:{NAME_W}px;width:{NAME_W}px;max-width:{NAME_W}px;'
            f'height:{ROW_H}px;padding:4px 6px;background:{rbg};'
            f'border-right:2px solid #cbd5e1;border-bottom:1px solid #e2e8f0;'
            f'white-space:nowrap;overflow:hidden;">'
            f'<div style="display:flex;align-items:center;gap:5px">'
            f'<div style="flex-shrink:0;width:22px;height:22px;border-radius:50%;'
            f'background:{color}22;color:{color};border:1.5px solid {color}66;'
            f'display:flex;align-items:center;justify-content:center;'
            f'font-weight:800;font-size:8px">{initials}</div>'
            f'<span style="font-size:11px;font-weight:600;color:#334155;'
            f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{full_name}">'
            f'{last_name}</span>'
            f'</div></td>'
        )

        for dn in range(1, num_days + 1):
            d        = date(year, month, dn)
            is_wknd  = d.weekday() >= 5
            is_hol   = d in holidays
            is_tod   = d == today
            atype    = udays.get(dn)

            if atype:
                abg, afg, aletter = TYPE_STYLE.get(atype, ("#f1f5f9", "#64748b", "?"))
                inner = (
                    f'<div style="width:30px;height:30px;margin:0 auto;border-radius:6px;'
                    f'background:{abg};border:1.5px solid {afg}66;'
                    f'display:flex;align-items:center;justify-content:center;'
                    f'font-size:12px;font-weight:800;color:{afg}">{aletter}</div>'
                )
            elif is_hol:
                inner = '<div style="text-align:center;font-size:15px;color:#f59e0b">★</div>'
            elif is_wknd:
                inner = '<div style="width:18px;height:3px;margin:0 auto;background:#d1d5db;border-radius:2px"></div>'
            else:
                inner = ''

            if is_tod:
                cbg = "#eff6ff"
                brd = "border-left:2px solid #1d4ed8;border-right:2px solid #1d4ed8;"
            elif is_hol:
                cbg = "#fefce8"; brd = ""
            elif is_wknd:
                cbg = "#f1f5f9"; brd = ""
            else:
                cbg = rbg; brd = ""

            cells.append(
                f'<td style="min-width:{DAY_W}px;width:{DAY_W}px;max-width:{DAY_W}px;'
                f'height:{ROW_H}px;text-align:center;vertical-align:middle;padding:0 1px;'
                f'background:{cbg};{brd}border-bottom:1px solid #e2e8f0;">{inner}</td>'
            )

        rows.append(f'<tr>{"".join(cells)}</tr>')

    # Sestavení kompletní tabulky
    table_html = (
        '<div style="overflow-x:auto;-webkit-overflow-scrolling:touch;'
        'border:1px solid #e2e8f0;border-radius:12px;'
        'box-shadow:0 2px 8px rgba(31,94,140,.08)">'
        '<table style="border-collapse:collapse;font-family:Inter,sans-serif;'
        'min-width:max-content;width:100%">'
        '<thead>' + rows[0] + '</thead>'
        '<tbody>' + "".join(rows[1:]) + '</tbody>'
        '</table></div>'
    )
    st.markdown(table_html, unsafe_allow_html=True)

    # ── Souhrn ──────────────────────────────────────────────────
    type_totals = {}
    for a in absences:
        t   = a["absence_type"]
        af  = max(date.fromisoformat(a["date_from"]), first)
        at  = min(date.fromisoformat(a["date_to"]),   last)
        type_totals[t] = type_totals.get(t, 0) + count_workdays_in_range(af, at)

    sum_parts = ['<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:16px">']
    for typ, tbg, tfg, tlabel in [
        ("vacation",      "#dbeafe", "#1d4ed8", "🏖 Dovolená"),
        ("vacation_half", "#bfdbfe", "#1d4ed8", "🌅 Půlden"),
        ("sickday",       "#fee2e2", "#991b1b", "🤒 Sickday"),
        ("nemoc",         "#ffe4e6", "#9f1239", "🏥 Nemoc/PN"),
    ]:
        cnt = type_totals.get(typ, 0)
        sum_parts.append(
            f'<div style="background:{tbg};color:{tfg};border-radius:8px;'
            f'padding:7px 14px;font-size:13px;font-weight:700">'
            f'{tlabel} · {cnt} dní</div>'
        )

    # Státní svátky v měsíci
    hol_names = {
        (1,1):"Nový rok",(5,1):"Svátek práce",(5,8):"Den vítězství",
        (7,5):"Cyril a Metoděj",(7,6):"Mistr Jan Hus",(9,28):"Den české státnosti",
        (10,28):"Vznik ČSR",(11,17):"Den boje za svobodu",
        (12,24):"Štědrý den",(12,25):"1. svátek vánoční",
        (12,26):"2. svátek vánoční",
    }
    for h in sorted(d for d in holidays if d.month == month and d.year == year):
        name = hol_names.get((h.month, h.day), "Státní svátek")
        sum_parts.append(
            f'<div style="background:#fef9c3;color:#92400e;border-radius:8px;'
            f'padding:7px 14px;font-size:13px;font-weight:700">'
            f'★ {h.day}. – {name}</div>'
        )
    sum_parts.append('</div>')
    st.markdown("".join(sum_parts), unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


def inject_czech_datepicker():
    """
    Lokalizuje Streamlit datepicker na češtinu + pondělí jako 1. den.
    Kombinuje CSS (order) a JS (MutationObserver + setInterval fallback).
    """
    st.markdown("""
    <style>
    /* Přesuň neděli (první sloupec) na konec – CSS order */
    [data-baseweb="calendar"] [role="row"],
    [data-baseweb="datepicker"] [role="row"] {
        display: flex !important;
        flex-wrap: nowrap !important;
    }
    [data-baseweb="calendar"] [role="row"] > *:first-child,
    [data-baseweb="datepicker"] [role="row"] > *:first-child {
        order: 7 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    _components.html("""
<script>
(function() {
    var D = window.parent ? window.parent.document : document;

    var DAY = {
        'Su':'Ne','Mo':'Po','Tu':'Út','We':'St','Th':'Čt','Fr':'Pá','Sa':'So',
        'Sunday':'Ne','Monday':'Po','Tuesday':'Út','Wednesday':'St',
        'Thursday':'Čt','Friday':'Pá','Saturday':'So'
    };
    var MON = {
        'January':'Leden','February':'Únor','March':'Březen','April':'Duben',
        'May':'Květen','June':'Červen','July':'Červenec','August':'Srpen',
        'September':'Září','October':'Říjen','November':'Listopad','December':'Prosinec'
    };

    function replaceText(node, map) {
        var t = (node.textContent || '').trim();
        if (map[t]) { node.textContent = map[t]; return; }
        // partial replace pro měsíc + rok ("January 2026")
        Object.keys(map).forEach(function(en) {
            if (t.indexOf(en) !== -1) {
                node.textContent = t.replace(en, map[en]);
            }
        });
    }

    function patch() {
        // Záhlaví dní (columnheader)
        D.querySelectorAll(
            '[data-baseweb="calendar"] [role="columnheader"],' +
            '[data-baseweb="datepicker"] [role="columnheader"],' +
            '[data-testid="stDateInputField"] [role="columnheader"]'
        ).forEach(function(el) { replaceText(el, DAY); });

        // Hlavička s měsícem a rokem – hledáme tlačítka i divy uvnitř kalendáře
        D.querySelectorAll(
            '[data-baseweb="calendar"] [role="heading"],' +
            '[data-baseweb="calendar"] [aria-live],' +
            '[data-baseweb="datepicker"] [role="heading"],' +
            '[data-baseweb="datepicker"] [aria-live],' +
            '[data-baseweb="calendar"] button,' +
            '[data-baseweb="datepicker"] button'
        ).forEach(function(el) { replaceText(el, MON); });

        // Select options pro výběr měsíce
        D.querySelectorAll(
            '[data-baseweb="select"] [role="option"],' +
            '[data-baseweb="menu"] [role="option"]'
        ).forEach(function(el) { replaceText(el, MON); });

        // Aria-label na dnech ("Sunday, January 5, 2026" → přepsat)
        D.querySelectorAll(
            '[data-baseweb="calendar"] [role="gridcell"],' +
            '[data-baseweb="datepicker"] [role="gridcell"]'
        ).forEach(function(el) {
            var lbl = el.getAttribute('aria-label') || '';
            Object.keys(DAY).forEach(function(en) {
                if (lbl.startsWith(en + ',')) {
                    el.setAttribute('aria-label', lbl.replace(en + ',', DAY[en] + ','));
                }
            });
            Object.keys(MON).forEach(function(en) {
                if (lbl.indexOf(en) !== -1) {
                    el.setAttribute('aria-label', lbl.replace(en, MON[en]));
                    lbl = el.getAttribute('aria-label');
                }
            });
        });
    }

    // Spusť ihned + setInterval fallback (každých 200 ms)
    patch();
    setInterval(patch, 200);

    // MutationObserver pro okamžitou reakci
    var obs = new MutationObserver(function(muts) {
        muts.forEach(function(m) {
            if (m.addedNodes.length) patch();
        });
    });
    obs.observe(D.body, { childList: true, subtree: true });
})();
</script>
""", height=0, scrolling=False)

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
init_db()

# Záloha při každém (re)startu aplikace
_do_backup('startup')
start_auto_backup()  # spustí daemon thread zálohy

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
            "📅 Kalendář":        "calendar",
            "🕐 Moje docházka":   "attendance",
            "🏖 Absence":         "absences",
            "✏️ Úpravy záznamu":  "corrections",
            "📈 Výkazy":          "reports",
        }
        if is_admin:
            _pend = get_pending_counts()
            _badge = f" 🔴 {_pend['total']}" if _pend["total"] > 0 else ""
            pages[f"⚙️ Správa{_badge}"] = "admin"

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

    # Injektuj českou lokalizaci kalendáře při každém renderu
    inject_czech_datepicker()

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
    elif page == "calendar":
        page_calendar()
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
