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

@employee_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        id_str = request.form.get("id")
        pwd = request.form.get("password")
        next_url = request.args.get("next") or url_for("index")
        try:
            emp_id = int(id_str)
        except (TypeError, ValueError):
            error = "ID غير صالح"
        else:
            ip = request.remote_addr or 'unknown'
            conn = get_conn()
            cur = conn.cursor()
            cur.execute('SELECT attempts,last_attempt FROM auth_failures WHERE ip=?', (ip,))
            af = cur.fetchone()
            locked = False
            if af:
                try:
                    last = datetime.fromisoformat(af[1])
                except Exception:
                    last = datetime.now()
                if af[0] >= 5 and (datetime.now() - last).total_seconds() < 15 * 60:
                    locked = True
            if locked:
                error = 'محظور مؤقتًا بعد محاولات فاشلة، حاول بعد قليل'
            else:
                cur.execute("SELECT id,name,password_hash,role FROM employees WHERE id=?", (emp_id,))
                row = cur.fetchone()
                if not row or not row[2] or not check_password_hash(row[2], pwd or ""):
                    error = "بيانات تسجيل الدخول غير صحيحة"
                    now_s = datetime.now().isoformat()
                    try:
                        cur.execute('INSERT INTO auth_failures(ip,attempts,last_attempt) VALUES(?,?,?)', (ip, 1, now_s))
                    except Exception:
                        cur.execute('UPDATE auth_failures SET attempts=attempts+1,last_attempt=? WHERE ip=?', (now_s, ip))
                    cur.execute('INSERT INTO auth_logs(employee_id,ip,action,success,timestamp) VALUES(?,?,?,?,?)', (emp_id, ip, 'login', 0, datetime.now().isoformat()))
                    conn.commit()
                else:
                    cur.execute('DELETE FROM auth_failures WHERE ip=?', (ip,))
                    session["employee_id"] = row[0]
                    session["employee_name"] = row[1]
                    session["employee_role"] = row[3] or "employee"
                    
                    if session["employee_role"] == "manager":
                        today_str = datetime.now().strftime('%Y-%m-%d')
                        backup_file = os.path.join(BACKUPS_DIR, f"verde_clinic_backup_{today_str}.db")
                        if not os.path.exists(backup_file):
                            try:
                                os.makedirs(BACKUPS_DIR, exist_ok=True)
                                shutil.copy2(DB_PATH, backup_file)
                                for f in os.listdir(BACKUPS_DIR):
                                    f_path = os.path.join(BACKUPS_DIR, f)
                                    if os.path.isfile(f_path):
                                        f_date_str = f.replace('verde_clinic_backup_', '').replace('.db', '')
                                        try:
                                            f_date = datetime.strptime(f_date_str, '%Y-%m-%d')
                                            if (datetime.now() - f_date).days > 7:
                                                os.remove(f_path)
                                        except: pass
                            except Exception: pass

                    cur.execute('INSERT INTO auth_logs(employee_id,ip,action,success,timestamp) VALUES(?,?,?,?,?)', (row[0], ip, 'login', 1, datetime.now().isoformat()))
                    conn.commit()
                    conn.close()
                    return redirect(next_url)
            conn.commit()
            conn.close()
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
