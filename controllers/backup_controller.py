import os
import shutil
import sqlite3
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, send_file, request
from werkzeug.utils import secure_filename
from db import get_conn, DB_PATH, BACKUPS_DIR
from auth import manager_required

backup_bp = Blueprint('backup', __name__)

def perform_safe_restore(source_file_path):
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    # 1. Create safety backup of current database
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    safety_backup = os.path.join(BACKUPS_DIR, f"safety_before_restore_{now_str}.db")
    if os.path.exists(DB_PATH):
        try:
            shutil.copy2(DB_PATH, safety_backup)
        except Exception:
            pass

    # 2. Perform online SQLite backup/restore from source_file_path to DB_PATH
    src_conn = sqlite3.connect(source_file_path)
    dst_conn = sqlite3.connect(DB_PATH)
    src_conn.backup(dst_conn)
    src_conn.close()
    dst_conn.close()

    # 3. Also copy file directly to ensure full alignment
    shutil.copy2(source_file_path, DB_PATH)

    # 4. Clean up any stale -wal and -shm files for DB_PATH
    for ext in ['-wal', '-shm']:
        wal_file = DB_PATH + ext
        if os.path.exists(wal_file):
            try:
                os.remove(wal_file)
            except Exception:
                pass

    # 5. Ensure missing columns/tables are auto-migrated
    from db import init_db
    init_db()

@backup_bp.route("/backups")
@manager_required
def backups_list():
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    files = sorted([f for f in os.listdir(BACKUPS_DIR) if f.endswith('.db')], reverse=True)
    return render_template("backups.html", files=files)

@backup_bp.route("/backups/create")
@manager_required
def backup_create():
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    now_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_file = os.path.join(BACKUPS_DIR, f"verde_clinic_backup_{now_str}.db")
    try:
        conn = get_conn()
        backup_conn = sqlite3.connect(backup_file)
        conn.backup(backup_conn)
        conn.close()
        backup_conn.close()
        flash("تم إنشاء النسخة الاحتياطية بنجاح", "success")
    except Exception as e:
        flash(f"حدث خطأ أثناء إنشاء النسخة الاحتياطية: {e}", "danger")
    return redirect(url_for("backup.backups_list"))

@backup_bp.route("/backups/upload", methods=["POST"])
@manager_required
def backup_upload():
    if 'backup_file' not in request.files:
        flash("لم يتم اختيار أي ملف", "danger")
        return redirect(url_for("backup.backups_list"))
    
    file = request.files['backup_file']
    if not file or file.filename == '':
        flash("يرجى اختيار ملف نسخة احتياطية صالح", "danger")
        return redirect(url_for("backup.backups_list"))
    
    filename = file.filename
    if not filename.lower().endswith('.db'):
        filename += '.db'
    
    safe_fname = secure_filename(filename)
    if not safe_fname:
        safe_fname = f"uploaded_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    elif not safe_fname.endswith('.db'):
        safe_fname += '.db'

    os.makedirs(BACKUPS_DIR, exist_ok=True)
    target_path = os.path.join(BACKUPS_DIR, safe_fname)
    
    file.save(target_path)
    
    # Validate SQLite header magic bytes
    try:
        with open(target_path, 'rb') as f:
            header = f.read(16)
        if not header.startswith(b'SQLite format 3'):
            os.remove(target_path)
            flash("الملف المرفوع ليس ملف قاعدة بيانات SQLite صالح!", "danger")
            return redirect(url_for("backup.backups_list"))
    except Exception as e:
        if os.path.exists(target_path):
            os.remove(target_path)
        flash(f"حدث خطأ أثناء قراءة الملف: {e}", "danger")
        return redirect(url_for("backup.backups_list"))

    auto_restore = request.form.get("auto_restore") == "1"
    
    if auto_restore:
        try:
            perform_safe_restore(target_path)
            flash("تم رفع الملف بنجاح واستعادة قاعدة البيانات فوراً في النظام!", "success")
        except Exception as e:
            flash(f"تم رفع الملف بنجاح ولكن حدث خطأ أثناء الاستعادة: {e}", "warning")
    else:
        flash("تم رفع ملف النسخة الاحتياطية وإضافته إلى السجل بنجاح", "success")

    return redirect(url_for("backup.backups_list"))

@backup_bp.route("/backups/download/<path:fname>")
@manager_required
def backup_download(fname):
    fpath = os.path.join(BACKUPS_DIR, fname)
    if not os.path.isfile(fpath):
        flash("الملف غير موجود", "danger")
        return redirect(url_for("backup.backups_list"))
    return send_file(fpath, as_attachment=True)

@backup_bp.route("/backups/delete/<path:fname>")
@manager_required
def backup_delete(fname):
    fpath = os.path.join(BACKUPS_DIR, fname)
    if os.path.isfile(fpath):
        try:
            os.remove(fpath)
            flash("تم حذف النسخة الاحتياطية", "success")
        except Exception as e:
            flash(f"تعذر حذف الملف: {e}", "danger")
    return redirect(url_for("backup.backups_list"))

@backup_bp.route("/backups/restore/<path:fname>")
@manager_required
def backup_restore(fname):
    fpath = os.path.join(BACKUPS_DIR, fname)
    if not os.path.isfile(fpath):
        flash("الملف غير موجود", "danger")
        return redirect(url_for("backup.backups_list"))
    try:
        perform_safe_restore(fpath)
        flash("تم استعادة قاعدة البيانات بنجاح في النظام من النسخة الاحتياطية المختارة", "success")
    except Exception as e:
        flash(f"حدث خطأ أثناء استعادة قاعدة البيانات: {e}", "danger")
    return redirect(url_for("backup.backups_list"))
