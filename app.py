import os
import json
import time
import shutil
import threading
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session

from dotenv import load_dotenv
load_dotenv()

from db import get_conn, init_db, seed_packages, DB_PATH
from auth import login_required
from models import Package, WhatsAppSettings

# Import controllers and blueprints
from controllers.customer_controller import (
    customer_search, customer_detail, register_customer,
    add_booking_to_customer, delete_customer, update_customer_medical
)
from controllers.employee_controller import employee_bp
from controllers.booking_controller import booking_bp
from controllers.report_controller import report_bp
from controllers.backup_controller import backup_bp
from controllers.expense_controller import expense_bp
from controllers.whatsapp_controller import whatsapp_bp

app = Flask(__name__)

# Secret key configuration with persistent fallback
secret_key = os.environ.get("POS_SECRET")
if not secret_key:
    secret_key = "zara_beauty_clinic_secure_persistent_secret_key_2026"
app.secret_key = secret_key

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE=os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax'),
    SESSION_COOKIE_SECURE=(os.environ.get('USE_HTTPS', '0') == '1')
)


@app.template_filter('whatsapp_phone')
def whatsapp_phone_filter(phone):
    if not phone:
        return ""
    phone = str(phone).strip()
    phone = "".join(c for c in phone if c.isdigit())
    if phone.startswith('00'):
        phone = phone[2:]
    if phone.startswith('200'):
        phone = '2' + phone[2:]
    if phone.startswith('01') and len(phone) == 11:
        phone = '2' + phone
    elif phone.startswith('1') and len(phone) == 10:
        phone = '20' + phone
    return phone


def whatsapp_background_agent():
    while True:
        try:
            with app.app_context():
                settings = WhatsAppSettings.get_settings()
                if settings and settings.get('is_active') == 1:
                    instance_id = settings.get('instance_id')
                    api_token = settings.get('api_token')
                    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute('''
                        SELECT b.id, c.name, c.phone, p.name 
                        FROM bookings b
                        JOIN customers c ON b.customer_id = c.id
                        JOIN packages p ON b.package_id = p.id
                        WHERE b.next_session_date = ? AND b.reminder_sent = 0
                    ''', (tomorrow,))
                    reminders = cur.fetchall()

                    for rid, cname, cphone, pname in reminders:
                        formatted_phone = whatsapp_phone_filter(cphone)
                        msg = f"مرحباً {cname}، نذكرك بموعد جلستك القادمة ({pname}) غداً في مركزنا. ننتظرك بكل حب."

                        success = False
                        error_msg = ""
                        try:
                            if instance_id and "instance" in instance_id:
                                url = f"https://api.ultramsg.com/{instance_id}/messages/chat"
                                payload = {"token": api_token, "to": formatted_phone, "body": msg}
                                response = requests.post(url, data=payload, timeout=10)
                                if response.status_code == 200:
                                    res_json = response.json()
                                    if res_json.get('sent') == 'true' or res_json.get('id'):
                                        success = True
                                    else:
                                        error_msg = f"UltraMsg Error: {response.text}"
                                else:
                                    error_msg = f"UltraMsg HTTP Error: {response.status_code}"
                            elif instance_id:
                                status_url = f"https://api.green-api.com/waInstance{instance_id}/getStateInstance/{api_token}"
                                try:
                                    status_resp = requests.get(status_url, timeout=5)
                                    if status_resp.status_code == 200:
                                        state = status_resp.json().get('stateInstance')
                                        if state != 'authorized':
                                            error_msg = f"Green-API: الرقم غير متصل ({state})."
                                            raise Exception(error_msg)
                                except Exception as e:
                                    if "Green-API:" in str(e):
                                        raise e

                                url = f"https://api.green-api.com/waInstance{instance_id}/sendMessage/{api_token}"
                                payload = {"chatId": f"{formatted_phone}@c.us", "message": msg}
                                response = requests.post(url, json=payload, timeout=10)
                                if response.status_code == 200:
                                    res_json = response.json()
                                    if res_json.get('idMessage'):
                                        success = True
                                    else:
                                        error_msg = f"Green-API Error: {response.text}"
                                else:
                                    error_msg = f"Green-API HTTP Error: {response.status_code}"

                            if success:
                                cur.execute("UPDATE bookings SET reminder_sent = 1 WHERE id = ?", (rid,))
                                cur.execute("INSERT INTO notifications (message, type) VALUES (?, ?)",
                                            (f"تم إرسال تذكير لـ {cname} ({formatted_phone})", "success"))
                            else:
                                cur.execute("INSERT INTO notifications (message, type) VALUES (?, ?)",
                                            (f"فشل إرسال تذكير لـ {cname} ({formatted_phone}): {error_msg[:100]}", "danger"))
                            conn.commit()
                            time.sleep(3)
                        except Exception as e:
                            print(f"Error sending WhatsApp to {cphone}: {e}")
                            cur.execute("INSERT INTO notifications (message, type) VALUES (?, ?)",
                                        (f"خطأ تقني في إرسال تذكير لـ {cname}: {str(e)[:100]}", "danger"))
                            conn.commit()
                    conn.close()
        except Exception as e:
            print(f"Background Agent Error: {e}")
        time.sleep(3600)


@app.context_processor
def inject_global_vars():
    res = {'allow_public_signup': False, 'unread_count': 0, 'notifications': []}
    if request.path.startswith('/static'):
        return res
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM employees')
        cnt = cur.fetchone()[0]
        res['allow_public_signup'] = (cnt == 0)

        if session.get('employee_id'):
            cur.execute('SELECT COUNT(*) FROM notifications WHERE is_read = 0')
            res['unread_count'] = cur.fetchone()[0]
            cur.execute('SELECT id, message, type, created_at FROM notifications ORDER BY created_at DESC LIMIT 5')
            res['notifications'] = cur.fetchall()
        conn.close()
    except Exception:
        pass
    return res


# ------------------------------
# Register Blueprints
# ------------------------------
app.register_blueprint(employee_bp)
app.register_blueprint(booking_bp)
app.register_blueprint(report_bp)
app.register_blueprint(backup_bp)
app.register_blueprint(expense_bp)
app.register_blueprint(whatsapp_bp)

# ------------------------------
# Customer Controller URL Rules
# ------------------------------
app.add_url_rule('/customer', 'customer_search', customer_search, methods=['GET'])
app.add_url_rule('/customer/<int:customer_id>', 'customer', customer_detail, methods=['GET'])
app.add_url_rule('/customer/<int:customer_id>', 'customer_detail', customer_detail, methods=['GET'])
app.add_url_rule('/register', 'register', register_customer, methods=['GET', 'POST'])
app.add_url_rule('/customer/<int:customer_id>/add_booking', 'add_booking_existing', add_booking_to_customer, methods=['POST'])
app.add_url_rule('/customers/<int:customer_id>/delete', 'delete_customer', delete_customer, methods=['POST'])
app.add_url_rule('/customer/<int:customer_id>/update_medical', 'update_customer_medical', update_customer_medical, methods=['POST'])

# Endpoint aliases for template compatibility
if 'employee.login' in app.view_functions:
    app.add_url_rule('/login', 'login', view_func=app.view_functions['employee.login'], methods=['GET', 'POST'])
if 'employee.logout' in app.view_functions:
    app.add_url_rule('/logout', 'logout', view_func=app.view_functions['employee.logout'])
if 'employee.signup' in app.view_functions:
    app.add_url_rule('/signup', 'signup', view_func=app.view_functions['employee.signup'], methods=['GET', 'POST'])
if 'employee.employees' in app.view_functions:
    app.add_url_rule('/employees', 'employees', view_func=app.view_functions['employee.employees'], methods=['GET', 'POST'])
if 'report.dashboard' in app.view_functions:
    app.add_url_rule('/dashboard', 'dashboard', view_func=app.view_functions['report.dashboard'])
if 'report.packages_admin' in app.view_functions:
    app.add_url_rule('/packages', 'packages_admin', view_func=app.view_functions['report.packages_admin'], methods=['GET', 'POST'])
if 'expense.expenses' in app.view_functions:
    app.add_url_rule('/expenses', 'expenses', view_func=app.view_functions['expense.expenses'])
if 'backup.backups_list' in app.view_functions:
    app.add_url_rule('/backups', 'backups_list', view_func=app.view_functions['backup.backups_list'])
if 'backup.backup_create' in app.view_functions:
    app.add_url_rule('/backups/create', 'backup_create', view_func=app.view_functions['backup.backup_create'])
if 'backup.backup_download' in app.view_functions:
    app.add_url_rule('/backups/download/<path:fname>', 'backup_download', view_func=app.view_functions['backup.backup_download'])
if 'backup.backup_delete' in app.view_functions:
    app.add_url_rule('/backups/delete/<path:fname>', 'backup_delete', view_func=app.view_functions['backup.backup_delete'])
if 'backup.backup_restore' in app.view_functions:
    app.add_url_rule('/backups/restore/<path:fname>', 'backup_restore', view_func=app.view_functions['backup.backup_restore'])
if 'backup.backup_upload' in app.view_functions:
    app.add_url_rule('/backups/upload', 'backup_upload', view_func=app.view_functions['backup.backup_upload'], methods=['POST'])
if 'whatsapp.read_all_notifications' in app.view_functions:
    app.add_url_rule('/notifications/read_all', 'read_all_notifications', view_func=app.view_functions['whatsapp.read_all_notifications'])


@app.route("/")
def index():
    if not session.get("employee_id"):
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute('SELECT COUNT(*) FROM employees')
            cnt = cur.fetchone()[0]
            conn.close()
            if cnt == 0:
                return redirect(url_for("signup"))
        except Exception:
            pass
        return redirect(url_for("login"))

    cosmetic_sessions = Package.find_by_category("cosmetic_sessions")
    cosmetic_packages = Package.find_by_category("cosmetic_packages")
    laser_sessions = Package.find_by_category("laser_sessions")
    laser_packages = Package.find_by_category("laser_packages")
    pulse_packages = Package.find_by_category("pulse_packages")
    return render_template("index.html", 
                         cosmetic_sessions=[(p['id'], p['name'], p['price']) for p in cosmetic_sessions],
                         cosmetic_packages=[(p['id'], p['name'], p['price']) for p in cosmetic_packages],
                         laser_sessions=[(p['id'], p['name'], p['price']) for p in laser_sessions],
                         laser_packages=[(p['id'], p['name'], p['price']) for p in laser_packages],
                         pulse_packages=[(p['id'], p['name'], p['price']) for p in pulse_packages])


if __name__ == "__main__":
    init_db()
    seed_packages()

    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        agent_thread = threading.Thread(target=whatsapp_background_agent, daemon=True)
        agent_thread.start()

    port = int(os.environ.get("PORT", 5007))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
