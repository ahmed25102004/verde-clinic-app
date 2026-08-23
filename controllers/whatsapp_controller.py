import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from db import get_conn
from auth import login_required, manager_required
from models import WhatsAppSettings

whatsapp_bp = Blueprint('whatsapp', __name__)

@whatsapp_bp.route("/settings/whatsapp", methods=["GET", "POST"])
@manager_required
def whatsapp_settings_page():
    if request.method == "POST":
        instance_id = request.form.get("instance_id")
        api_token = request.form.get("api_token")
        sender_phone = request.form.get("sender_phone")
        is_active = 1 if request.form.get("is_active") == "on" else 0
        WhatsAppSettings.update_settings(instance_id, api_token, sender_phone, is_active)
        flash("تم حفظ إعدادات الواتساب بنجاح", "success")
    settings = WhatsAppSettings.get_settings()
    return render_template("whatsapp_settings.html", settings=settings)

@whatsapp_bp.route("/notifications/read_all")
@manager_required
def read_all_notifications():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE notifications SET is_read = 1")
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('report.dashboard'))

@whatsapp_bp.route('/check_phone')
@login_required
def check_phone():
    phone = request.args.get('phone') or ''
    phone = ''.join(c for c in phone if c.isdigit())
    if not phone:
        return Response(json.dumps({'exists': False}), status=200, mimetype='application/json')
    if not phone.isdigit() or len(phone) != 11:
        return Response(json.dumps({'error': 'رقم الموبايل يجب أن يكون 11 رقمًا'}), status=400, mimetype='application/json')
    
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM customers WHERE phone = ?", (phone,))
    exists = bool(cur.fetchone())
    conn.close()
    return Response(json.dumps({'exists': exists}), status=200, mimetype='application/json')
