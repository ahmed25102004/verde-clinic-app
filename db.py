
import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(__file__), "verde_clinic.db")
EXPORTS_DIR = os.path.join(os.path.dirname(__file__), "exports")
BACKUPS_DIR = os.path.join(os.path.dirname(__file__), "backups")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # Create tables if not exist
    cur.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        note TEXT,
        created_at TEXT NOT NULL,
        medical_notes TEXT,
        allergies TEXT,
        preferences TEXT,
        medical_conditions TEXT
    )
    """)
    
    # Add new columns if they don't exist (for existing databases)
    try:
        cur.execute("ALTER TABLE customers ADD COLUMN medical_notes TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cur.execute("ALTER TABLE customers ADD COLUMN allergies TEXT")
    except sqlite3.OperationalError:
        pass
    
    try:
        cur.execute("ALTER TABLE customers ADD COLUMN preferences TEXT")
    except sqlite3.OperationalError:
        pass
    
    try:
        cur.execute("ALTER TABLE customers ADD COLUMN medical_conditions TEXT")
    except sqlite3.OperationalError:
        pass

    cur.execute("""
    CREATE TABLE IF NOT EXISTS packages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        name TEXT NOT NULL,
        sessions_count INTEGER NOT NULL,
        price INTEGER NOT NULL,
        bonus TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        package_id INTEGER NOT NULL,
        total_sessions INTEGER NOT NULL,
        sessions_done INTEGER NOT NULL DEFAULT 0,
        start_date TEXT NOT NULL,
        employee_id INTEGER,
        pulses_total INTEGER DEFAULT 0,
        pulses_used INTEGER DEFAULT 0,
        price_override INTEGER,
        next_session_date TEXT,
        reminder_sent INTEGER DEFAULT 0,
        FOREIGN KEY (customer_id) REFERENCES customers(id),
        FOREIGN KEY (package_id) REFERENCES packages(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER NOT NULL,
        session_number INTEGER NOT NULL,
        date TEXT NOT NULL,
        employee_id INTEGER,
        pulses_used INTEGER DEFAULT 0,
        note TEXT,
        FOREIGN KEY (booking_id) REFERENCES bookings(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        password_hash TEXT,
        role TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        method TEXT NOT NULL,
        date TEXT NOT NULL,
        employee_id INTEGER,
        FOREIGN KEY (booking_id) REFERENCES bookings(id),
        FOREIGN KEY (employee_id) REFERENCES employees(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS auth_failures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip TEXT UNIQUE,
        attempts INTEGER DEFAULT 0,
        last_attempt TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS auth_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER,
        ip TEXT,
        action TEXT,
        success INTEGER,
        timestamp TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT NOT NULL,
        amount INTEGER NOT NULL,
        category TEXT NOT NULL,
        date TEXT NOT NULL,
        employee_id INTEGER,
        FOREIGN KEY (employee_id) REFERENCES employees(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT NOT NULL,
        type TEXT DEFAULT 'info',
        is_read INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS whatsapp_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        instance_id TEXT NOT NULL,
        api_token TEXT NOT NULL,
        sender_phone TEXT,
        is_active INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


def seed_packages():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM packages")
    count = cur.fetchone()[0]
    if count == 0:
        data = [
            ("cosmetic_packages", "التقشير البارد للبشرة (جلستين)", 2, 700, None),
            ("cosmetic_packages", "التقشير البارد للبشرة (3 جلسات)", 3, 1000, None),
            ("cosmetic_packages", "ديرما بن بالميزوثيرابي (جلستين)", 2, 500, None),
            ("cosmetic_packages", "ديرما بن بالميزوثيرابي (3 جلسات)", 3, 700, None),
            ("cosmetic_packages", "الفراكشنال ليزر (3 جلسات)", 3, 1000, None),
            ("cosmetic_packages", "توريد الشفايف (جلستين)", 2, 400, None),
            ("cosmetic_packages", "تنظيف البشرة المرحلة الثالثة VIP (جلستين)", 2, 500, None),
            ("cosmetic_sessions", "التقشير البارد للبشرة", 1, 400, None),
            ("cosmetic_sessions", "ديرما بن بالميزوثيرابي", 1, 300, None),
            ("cosmetic_sessions", "الفراكشنال ليزر", 1, 400, None),
            ("cosmetic_sessions", "حقنة العنبر", 1, 800, None),
            ("cosmetic_sessions", "اسكين بوستر", 1, 1500, None),
            ("cosmetic_sessions", "توريد الشفايف", 1, 250, None),
            ("cosmetic_sessions", "البلازما", 1, 350, None),
            ("cosmetic_sessions", "تنظيف البشرة الأولى", 1, 150, None),
            ("cosmetic_sessions", "تنظيف البشرة الثانية", 1, 250, None),
            ("cosmetic_sessions", "تنظيف البشرة الثالثة VIP", 1, 300, None),
            ("pulse_packages", "1000 نبضة + 150 نبضة هدية", 1, 400, None),
            ("pulse_packages", "2300 نبضة + 150 نبضة هدية", 1, 900, None),
            ("pulse_packages", "3000 نبضة + بيكيني ولاين واندر ارم هدية", 1, 1250, None),
            ("pulse_packages", "5100 نبضة + 600 نبضة هدية", 1, 2000, None),
            ("pulse_packages", "7000 نبضة + 1100 نبضة هدية", 1, 2700, None),
            ("pulse_packages", "11000 نبضة", 1, 3850, None),
            ("pulse_packages", "12000 نبضة + جلسة ديرما بن بالميزوثيرابي هدية", 1, 4300, None),
            ("laser_sessions", "جلسة جسم كامل ببطن وظهر", 1, 1800, None),
            ("laser_sessions", "جلسة جسم كامل بدون بطن وظهر", 1, 1500, None),
            ("laser_sessions", "جلسة رجل كاملة", 1, 800, None),
            ("laser_sessions", "جلسة ذراع كامل", 1, 600, None),
            ("laser_sessions", "جلسة نصف الرجل العلوي", 1, 500, None),
            ("laser_sessions", "جلسة نصف الرجل السفلي", 1, 400, None),
            ("laser_sessions", "جلسة نصف الذراع", 1, 300, None),
            ("laser_sessions", "جلسة بطن", 1, 400, None),
            ("laser_sessions", "جلسة ظهر", 1, 550, None),
            ("laser_sessions", "جلسة وجه ورقبة", 1, 160, None),
            ("laser_sessions", "جلسة وجه", 1, 130, None),
            ("laser_sessions", "جلسة موستاش", 1, 50, None),
            ("laser_sessions", "جلسة ذقن", 1, 50, None),
            ("laser_sessions", "جلسة كف اليد", 1, 50, None),
            ("laser_packages", "جسم كامل ببطن وظهر (3 جلسات + جلسة هدية)", 4, 5600, None),
            ("laser_packages", "جسم كامل بدون بطن وظهر (3 جلسات + جلسة هدية)", 4, 4800, None),
            ("laser_packages", "نصف الجسم Half Body (3 جلسات + جلسة هدية)", 4, 3000, None),
            ("laser_packages", "رجل كاملة (3 جلسات + جلسة هدية)", 4, 2850, None),
            ("laser_packages", "نصف الرجل العلوي (3 جلسات + جلسة هدية)", 4, 1500, None),
            ("laser_packages", "نصف الرجل السفلي (3 جلسات + جلسة هدية)", 4, 1350, None),
            ("laser_packages", "الذراع كامل (3 جلسات + جلسة هدية)", 4, 1400, None),
            ("laser_packages", "نصف الذراع (3 جلسات + جلسة هدية)", 4, 900, None),
            ("laser_packages", "بيكيني + لاين + اندر ارم (3 جلسات + جلسة هدية)", 4, 600, None),
            ("laser_packages", "بيكيني + لاين (3 جلسات + جلسة هدية)", 4, 450, None),
            ("laser_packages", "اندر ارم (3 جلسات + جلسة هدية)", 4, 250, None),
            ("laser_packages", "وجه ورقبة (3 جلسات + جلسة هدية)", 4, 500, None),
            ("laser_packages", "الوجه (3 جلسات + جلسة هدية)", 4, 350, None),
            ("laser_packages", "كف اليد (3 جلسات + جلسة هدية)", 4, 140, None),
            ("laser_packages", "الموستاش (3 جلسات + جلسة هدية)", 4, 140, None),
            ("laser_packages", "الذقن (3 جلسات + جلسة هدية)", 4, 140, None),
        ]
        cur.executemany("INSERT INTO packages(category,name,sessions_count,price,bonus) VALUES(?,?,?,?,?)", data)
        conn.commit()
    conn.close()
