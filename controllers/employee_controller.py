import os
import shutil
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_conn, DB_PATH, BACKUPS_DIR
from auth import login_required, manager_required

employee_bp = Blueprint('employee', __name__)

@employee_bp.route("/employees", methods=["GET", "POST"])
@login_required
def employees():
    conn = get_conn()
    cur = conn.cursor()
    error = None
    if request.method == "POST":
        if session.get("employee_role") != "manager":
            error = "غير مسموح: المدير فقط يستطيع إضافة موظف"
        else:
            name = request.form.get("name")
            id_str = request.form.get("id")
            pwd = request.form.get("password")
            role = request.form.get("role") or "employee"
            if not name or not id_str:
                error = "يرجى إدخال الاسم وID"
            else:
                try:
                    emp_id = int(id_str)
                    cur.execute("SELECT 1 FROM employees WHERE id=?", (emp_id,))
                    if cur.fetchone():
                        error = "المعرف مستخدم مسبقًا"
                    else:
                        ph = generate_password_hash(pwd) if pwd else None
                        cur.execute("INSERT INTO employees(id,name,password_hash,role) VALUES(?,?,?,?)", (emp_id, name, ph, role))
                        conn.commit()
                except ValueError:
                    error = "يرجى إدخال ID رقم صحيح"
    cur.execute("SELECT e.id, e.name, e.role FROM employees e ORDER BY id DESC")
    employees_list = cur.fetchall()
    conn.close()
    return render_template("employees.html", employees=employees_list, error=error)

@employee_bp.route("/employees/delete", methods=["POST"])
@login_required
def employees_delete():
    emp_id = request.form.get("id")
    if not emp_id:
        return redirect(url_for("employee.employees"))
    try:
        eid = int(emp_id)
    except ValueError:
        return redirect(url_for("employee.employees"))

    current_id = session.get("employee_id")
    role = session.get("employee_role")

    conn = get_conn()
    cur = conn.cursor()

    if eid != current_id and role != "manager":
        try:
            cur.execute('INSERT INTO auth_logs(employee_id,ip,action,success,timestamp) VALUES(?,?,?,?,?)', 
                        (current_id, request.remote_addr or 'unknown', 'delete_account', 0, datetime.now().isoformat()))
            conn.commit()
        except Exception:
            pass
        conn.close()
        return ("Unauthorized Access", 401)

    if eid == current_id:
        confirm_id = request.form.get("confirm_id")
        confirm_pwd = request.form.get("confirm_password")
        if not confirm_id or not confirm_pwd:
            cur.execute("SELECT id,name,role FROM employees ORDER BY id DESC")
            employees_list = cur.fetchall()
            conn.close()
            error = "بيانات غير صحيحة، لا يمكن حذف الحساب"
            return render_template("employees.html", employees=employees_list, error=error)
        try:
            confirm_eid = int(confirm_id)
        except ValueError:
            cur.execute("SELECT id,name,role FROM employees ORDER BY id DESC")
            employees_list = cur.fetchall()
            conn.close()
            error = "بيانات غير صحيحة، لا يمكن حذف الحساب"
            return render_template("employees.html", employees=employees_list, error=error)
        if confirm_eid != current_id:
            cur.execute("SELECT id,name,role FROM employees ORDER BY id DESC")
            employees_list = cur.fetchall()
            conn.close()
            error = "بيانات غير صحيحة، لا يمكن حذف الحساب"
            return render_template("employees.html", employees=employees_list, error=error)
        cur.execute("SELECT password_hash FROM employees WHERE id=?", (current_id,))
        row = cur.fetchone()
        if not row or not row[0] or not check_password_hash(row[0], confirm_pwd):
            cur.execute("SELECT id,name,role FROM employees ORDER BY id DESC")
            employees_list = cur.fetchall()
            conn.close()
            error = "كلمة المرور غير صحيحة"
            return render_template("employees.html", employees=employees_list, error=error)

    cur.execute("DELETE FROM employees WHERE id=?", (eid,))
    cur.execute('INSERT INTO auth_logs(employee_id,ip,action,success,timestamp) VALUES(?,?,?,?,?)', 
                (current_id, request.remote_addr or 'unknown', 'delete_account', 1, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    if eid == current_id:
        session.clear()
        return redirect(url_for("employee.login"))
    return redirect(url_for("employee.employees"))

def get_client_ip():
    if request.headers.get("CF-Connecting-IP"):
        return request.headers.get("CF-Connecting-IP").strip()
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    if request.headers.get("X-Real-IP"):
        return request.headers.get("X-Real-IP").strip()
    return request.remote_addr or "unknown"

def normalize_input(text):
    if not text:
        return ""
    text = str(text).strip()
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    english_digits = "0123456789"
    for a, e in zip(arabic_digits, english_digits):
        text = text.replace(a, e)
    return text.strip()

@employee_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        id_str = normalize_input(request.form.get("id"))
        pwd = (request.form.get("password") or "").strip()
        next_url = request.form.get("next") or request.args.get("next") or url_for("index")

        if not id_str:
            error = "يرجى إدخال ID الموظف"
        else:
            try:
                ip = get_client_ip()
                conn = get_conn()
                cur = conn.cursor()

                # Search by ID or Name/Role
                row = None
                if id_str.isdigit():
                    cur.execute("SELECT id, name, password_hash, role FROM employees WHERE id = ?", (int(id_str),))
                    row = cur.fetchone()
                if not row:
                    cur.execute("SELECT id, name, password_hash, role FROM employees WHERE LOWER(name) = LOWER(?) OR id = ?", (id_str, id_str))
                    row = cur.fetchone()

                is_valid = bool(row and row[2] and check_password_hash(row[2], pwd))

                if is_valid:
                    try:
                        print(f"[AUTH SUCCESS] Logged in: ID={row[0]}, Name='{row[1]}', IP='{ip}'", flush=True)
                    except Exception:
                        pass
                    # Successful login! Immediately delete any failed attempts for this IP
                    try:
                        cur.execute("DELETE FROM auth_failures WHERE ip = ?", (ip,))
                    except Exception:
                        pass

                    session.permanent = True
                    session["employee_id"] = row[0]
                    session["employee_name"] = row[1]
                    session["employee_role"] = row[3] or "employee"

                    try:
                        cur.execute(
                            "INSERT INTO auth_logs(employee_id, ip, action, success, timestamp) VALUES(?,?,?,?,?)",
                            (row[0], ip, "login", 1, datetime.now().isoformat())
                        )
                        conn.commit()
                    except Exception:
                        pass

                    conn.close()
                    return redirect(next_url)
                else:
                    # Invalid credentials: check failed attempts rate limit
                    cur.execute("SELECT attempts, last_attempt FROM auth_failures WHERE ip=?", (ip,))
                    af = cur.fetchone()

                    COOLDOWN_SECONDS = 60  # 1 minute lockout instead of 15 minutes
                    MAX_ATTEMPTS = 5
                    attempts = 0
                    last = datetime.now()

                    if af:
                        attempts = af[0] or 0
                        try:
                            last = datetime.fromisoformat(af[1])
                        except Exception:
                            last = datetime.now()

                        # Reset attempts counter if cooldown period has passed
                        if (datetime.now() - last).total_seconds() >= COOLDOWN_SECONDS:
                            attempts = 0

                    elapsed = (datetime.now() - last).total_seconds()
                    if attempts >= MAX_ATTEMPTS and elapsed < COOLDOWN_SECONDS:
                        remaining = int(COOLDOWN_SECONDS - elapsed)
                        try:
                            print(f"[AUTH BLOCKED] IP='{ip}' is rate-limited: {remaining}s remaining", flush=True)
                        except Exception:
                            pass
                        error = f"محظور مؤقتاً بسبب تكرار المحاولات الخاطئة. يرجى الانتظار {remaining} ثانية والمحاولة مجدداً."
                    else:
                        new_attempts = attempts + 1
                        now_s = datetime.now().isoformat()
                        try:
                            print(f"[AUTH FAILED] Failed login attempt: Input='{id_str}', IP='{ip}', Attempts={new_attempts}", flush=True)
                        except Exception:
                            pass
                        try:
                            cur.execute(
                                "INSERT INTO auth_failures(ip, attempts, last_attempt) VALUES(?,?,?)",
                                (ip, new_attempts, now_s)
                            )
                        except Exception:
                            try:
                                cur.execute(
                                    "UPDATE auth_failures SET attempts=?, last_attempt=? WHERE ip=?",
                                    (new_attempts, now_s, ip)
                                )
                            except Exception:
                                pass

                        try:
                            emp_record_id = row[0] if row else 0
                            cur.execute(
                                "INSERT INTO auth_logs(employee_id, ip, action, success, timestamp) VALUES(?,?,?,?,?)",
                                (emp_record_id, ip, "login", 0, datetime.now().isoformat())
                            )
                        except Exception:
                            pass

                        if new_attempts >= MAX_ATTEMPTS:
                            error = f"محظور مؤقتاً بعد 5 محاولات خاطئة. يرجى الانتظار {COOLDOWN_SECONDS} ثانية والمحاولة مجدداً."
                        else:
                            error = "بيانات تسجيل الدخول غير صحيحة"

                conn.commit()
                conn.close()
            except Exception as e:
                try:
                    print(f"Login error: {e}")
                except Exception:
                    pass
                error = "بيانات تسجيل الدخول غير صحيحة أو هناك خطأ في النظام"
    return render_template("login.html", error=error)

@employee_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("employee.login"))

@employee_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    employee_id = session.get("employee_id")
    conn = get_conn()
    cur = conn.cursor()
    
    if request.method == "POST":
        current_pwd = request.form.get("current_password")
        new_pwd = request.form.get("new_password")
        confirm_pwd = request.form.get("confirm_password")
        
        cur.execute("SELECT password_hash FROM employees WHERE id = ?", (employee_id,))
        user = cur.fetchone()
        
        if not user or not check_password_hash(user[0], current_pwd):
            flash("كلمة المرور الحالية غير صحيحة", "danger")
        elif not new_pwd or len(new_pwd) < 8:
            flash("كلمة المرور الجديدة يجب أن تكون 8 أحرف على الأقل", "danger")
        elif new_pwd != confirm_pwd:
            flash("تأكيد كلمة المرور لا يطابق كلمة المرور الجديدة", "danger")
        else:
            new_hash = generate_password_hash(new_pwd)
            cur.execute("UPDATE employees SET password_hash = ? WHERE id = ?", (new_hash, employee_id))
            conn.commit()
            flash("تم تغيير كلمة المرور بنجاح", "success")
            
    cur.execute("SELECT id, name, role FROM employees WHERE id = ?", (employee_id,))
    employee = cur.fetchone()
    
    cur.execute("SELECT COUNT(*) FROM sessions WHERE employee_id = ?", (employee_id,))
    sessions_count = cur.fetchone()[0]
    
    cur.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE employee_id = ?", (employee_id,))
    total_collected = cur.fetchone()[0]
    
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    cur.execute("SELECT COUNT(*) FROM sessions WHERE employee_id = ? AND date >= ?", (employee_id, month_ago))
    sessions_month = cur.fetchone()[0]
    
    cur.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE employee_id = ? AND date >= ?", (employee_id, month_ago))
    collected_month = cur.fetchone()[0]
    
    conn.close()
    
    return render_template("profile.html", 
                         employee=employee, 
                         sessions_count=sessions_count, 
                         total_collected=total_collected,
                         sessions_month=sessions_month,
                         collected_month=collected_month)

@employee_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM employees')
    cnt = cur.fetchone()[0]
    error = None
    if request.method == 'POST':
        if not (cnt == 0 or session.get('employee_role') == 'manager'):
            error = 'غير مسموح: تحتاج لتكون مديرًا لتنشئ حسابًا جديدًا'
        else:
            id_str = request.form.get('id')
            name = request.form.get('name')
            pwd = request.form.get('password')
            pwd2 = request.form.get('password_confirm')
            if not pwd or len(pwd) < 8:
                error = 'كلمة المرور قصيرة جدًا (8 أحرف على الأقل)'
            elif pwd != (pwd2 or ''):
                error = 'تأكيد كلمة المرور لا يطابق'
            else:
                role = request.form.get('role') or 'employee'
                try:
                    eid = int(id_str)
                except (TypeError, ValueError):
                    error = 'ID غير صالح'
                else:
                    cur.execute('SELECT 1 FROM employees WHERE id=?', (eid,))
                    if cur.fetchone():
                        error = 'هذا المعرف مستخدم بالفعل'
                    elif not name or not pwd:
                        error = 'يرجى إدخال الاسم وكلمة المرور'
                    else:
                        ph = generate_password_hash(pwd)
                        cur.execute('INSERT INTO employees(id,name,password_hash,role) VALUES(?,?,?,?)', (eid, name, ph, role))
                        cur.execute('INSERT INTO auth_logs(employee_id,ip,action,success,timestamp) VALUES(?,?,?,?,?)', (eid, request.remote_addr or 'unknown', 'create_account', 1, datetime.now().isoformat()))
                        conn.commit()
                        conn.close()
                        return redirect(url_for('employee.login'))
    conn.close()
    return render_template('signup.html', allow_public_signup=(cnt == 0), error=error)
