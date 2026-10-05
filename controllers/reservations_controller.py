import os
import json
import secrets
from datetime import datetime, date, time, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, abort
from db import get_conn
from auth import login_required, manager_required

reservations_bp = Blueprint("reservations", __name__)

def parse_time_str(s):
    if not s:
        return time(9, 0)
    try:
        return datetime.strptime(s.strip(), "%H:%M").time()
    except Exception:
        return time(9, 0)

def time_to_str(t):
    return t.strftime("%H:%M")

def add_minutes(t, minutes):
    dt = datetime.combine(date.today(), t) + timedelta(minutes=minutes)
    return dt.time()

def default_working_hours():
    return parse_time_str("09:00"), parse_time_str("21:00")

def overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end

def month_days(year, month):
    first = date(year, month, 1)
    next_month = date(year + (month // 12), (month % 12) + 1, 1)
    days = (next_month - first).days
    return [first + timedelta(days=i) for i in range(days)]

def resource_bookings(conn, resource_type, resource_id, day_str):
    cur = conn.cursor()
    if resource_type == "room":
        cur.execute("SELECT start_time, end_time FROM calendar_bookings WHERE day=? AND room_id=? AND status != 'canceled'", (day_str, resource_id))
    else:
        return []
    rows = cur.fetchall()
    return [(parse_time_str(r["start_time"]), parse_time_str(r["end_time"])) for r in rows]

def resource_downtimes(conn, resource_type, resource_id, day_str):
    cur = conn.cursor()
    cur.execute("SELECT start_time, end_time FROM downtimes WHERE day=? AND resource_type=? AND resource_id=?", (day_str, resource_type, resource_id))
    rows = cur.fetchall()
    return [(parse_time_str(r["start_time"]), parse_time_str(r["end_time"])) for r in rows]

def center_working_hours(conn, center_id, resource_type=None, resource_id=None):
    cur = conn.cursor()
    if resource_type and resource_id:
        cur.execute("""SELECT start_time, end_time FROM working_hours
                     WHERE resource_type=? AND resource_id=? ORDER BY id DESC LIMIT 1""", (resource_type, resource_id))
        r = cur.fetchone()
        if r:
            return parse_time_str(r["start_time"]), parse_time_str(r["end_time"])
    cur.execute("""SELECT start_time, end_time FROM working_hours
                 WHERE center_id=? AND resource_type IS NULL AND resource_id IS NULL
                 ORDER BY id DESC LIMIT 1""", (center_id,))
    r = cur.fetchone()
    if r:
        return parse_time_str(r["start_time"]), parse_time_str(r["end_time"])
    return default_working_hours()

def available_slots(conn, resource_type, resource_id, day_str, duration_minutes):
    cur = conn.cursor()
    if resource_type == "room":
        cur.execute("SELECT center_id FROM rooms WHERE id=?", (resource_id,))
    else:
        return []
    r = cur.fetchone()
    if not r: return []
    start, end = center_working_hours(conn, r["center_id"], resource_type, resource_id)
    slots = []
    bookings = resource_bookings(conn, resource_type, resource_id, day_str)
    downs = resource_downtimes(conn, resource_type, resource_id, day_str)
    t = start
    step = 15
    is_today = (day_str == date.today().isoformat())
    now_time = datetime.now().time()
    
    while (datetime.combine(date.today(), t) + timedelta(minutes=duration_minutes)).time() <= end:
        if is_today and t <= now_time:
            t = add_minutes(t, step)
            continue
        candidate_end = add_minutes(t, duration_minutes)
        conflict = False
        for b_start, b_end in bookings:
            if overlaps(t, candidate_end, b_start, b_end):
                conflict = True
                break
        if not conflict:
            for d_start, d_end in downs:
                if overlaps(t, candidate_end, d_start, d_end):
                    conflict = True
                    break
        if not conflict:
            slots.append((t, candidate_end))
        t = add_minutes(t, step)
    return slots

# -------------------------------------------------------------
# Calendar Views
# -------------------------------------------------------------
@reservations_bp.route("/reservations/calendar")
@login_required
def calendar():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM centers ORDER BY id LIMIT 1")
    center = cur.fetchone()
    center_id = center["id"] if center else 1

    cur.execute("SELECT * FROM session_types ORDER BY id")
    session_types = cur.fetchall()

    cur.execute("SELECT * FROM doctors WHERE active=1 ORDER BY name")
    doctors_rows = cur.fetchall()
    doctors_list = [dict(r) for r in doctors_rows]

    doctor_id = request.args.get("doctor_id", type=int)
    doctor = None
    if doctor_id:
        cur.execute("SELECT * FROM doctors WHERE id=?", (doctor_id,))
        doc_row = cur.fetchone()
        if doc_row:
            doctor = dict(doc_row)

    now = datetime.now()
    year = int(request.args.get("year", now.year))
    month = int(request.args.get("month", now.month))
    days = month_days(year, month)
    
    doctors_json = json.dumps({
        d['id']: {
            'available_days': d.get('available_days', ''),
            'color': d.get('color', '#0d6efd')
        } for d in doctors_list
    })

    conn.close()
    return render_template("reservations_calendar.html",
                           center_id=center_id,
                           types=session_types,
                           doctors_list=doctors_list,
                           doctors_json=doctors_json,
                           days=days,
                           year=year,
                           month=month,
                           today=date.today(),
                           doctor=doctor)

@reservations_bp.route("/reservations/day/<day_str>")
@login_required
def day_view(day_str):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id FROM centers ORDER BY id LIMIT 1")
    c_row = cur.fetchone()
    center_id = c_row["id"] if c_row else 1

    doctor_id = request.args.get("doctor_id", type=int)
    session_type_id = request.args.get("session_type_id", type=int)

    cur.execute("SELECT * FROM session_types ORDER BY id")
    types = cur.fetchall()

    cur.execute("SELECT * FROM doctors WHERE active=1 ORDER BY name")
    doctors = cur.fetchall()

    slots_by_resource = []
    duration = None
    day_dt = datetime.strptime(day_str, "%Y-%m-%d").date()
    is_past = day_dt < date.today()

    if session_type_id and not is_past:
        cur.execute("SELECT duration_minutes FROM session_types WHERE id=?", (session_type_id,))
        row = cur.fetchone()
        if row:
            duration = row["duration_minutes"]
            cur.execute("SELECT * FROM rooms WHERE center_id=?", (center_id,))
            rooms = cur.fetchall()
            for r in rooms:
                slots = available_slots(conn, "room", r["id"], day_str, duration)
                slots_by_resource.append(("room", r, slots))

    cur.execute("""SELECT b.*, st.name AS st_name, 
                 dc.name AS doctor_name, dc.color AS doctor_color,
                 COALESCE(r.name, '') AS room_name
                 FROM calendar_bookings b
                 JOIN session_types st ON st.id=b.session_type_id
                 LEFT JOIN rooms r ON r.id=b.room_id
                 LEFT JOIN doctors dc ON dc.id=b.doctor_id
                 WHERE b.day=? AND b.center_id=?""", (day_str, center_id))
    bookings = cur.fetchall()

    if doctor_id:
        bookings = [b for b in bookings if b["doctor_id"] == doctor_id]

    doc_query = """SELECT d.*, GROUP_CONCAT(dr.room_id) as assigned_rooms_str 
                   FROM doctors d 
                   LEFT JOIN doctor_rooms dr ON dr.doctor_id = d.id 
                   WHERE d.active=1 GROUP BY d.id"""
    cur.execute(doc_query)
    active_doctors = cur.fetchall()

    conn.close()
    return render_template("reservations_day.html",
                           day_str=day_str,
                           center_id=center_id,
                           doctor_id=doctor_id,
                           session_type_id=session_type_id,
                           types=types,
                           doctors=doctors,
                           duration=duration,
                           is_past=is_past,
                           slots_by_resource=slots_by_resource,
                           bookings=bookings)

# -------------------------------------------------------------
# Booking Operations
# -------------------------------------------------------------
@reservations_bp.route("/reservations/book", methods=["POST"])
@login_required
def book():
    conn = get_conn()
    cur = conn.cursor()
    
    center_id = request.form.get("center_id", type=int) or 1
    room_id = request.form.get("room_id", type=int)
    doctor_id = request.form.get("doctor_id", type=int)
    customer_name = request.form.get("customer_name", "").strip()
    area = request.form.get("area", "").strip()
    phone = request.form.get("phone", "").strip()
    session_type_id = request.form.get("session_type_id", type=int)
    day = request.form.get("day", "").strip()
    start_time = request.form.get("start_time", "").strip()

    if not customer_name or not session_type_id or not day or not start_time:
        flash("جميع البيانات الأساسية مطلوبة للحجز", "danger")
        conn.close()
        return redirect(url_for("reservations.day_view", day_str=day or date.today().isoformat()))

    cur.execute("SELECT duration_minutes FROM session_types WHERE id=?", (session_type_id,))
    st_row = cur.fetchone()
    if not st_row:
        flash("نوع الجلسة غير صحيح", "danger")
        conn.close()
        return redirect(url_for("reservations.day_view", day_str=day))

    duration = st_row["duration_minutes"]
    s_t = parse_time_str(start_time)
    e_t = add_minutes(s_t, duration)
    end_time = time_to_str(e_t)

    # Check for overlapping bookings in the same room
    if room_id:
        cur.execute("""SELECT id FROM calendar_bookings 
                     WHERE center_id=? AND day=? AND room_id=? AND status != 'canceled'
                     AND NOT(? >= end_time OR ? <= start_time)""",
                  (center_id, day, room_id, start_time, end_time))
        if cur.fetchone():
            flash("تنبيه: توجد حجز آخر متعارض في نفس الغرفة والتوقيت!", "danger")
            conn.close()
            return redirect(url_for("reservations.day_view", day_str=day))

    emp_id = session.get("employee_id")
    notes = request.form.get("notes", "")

    cur.execute("""INSERT INTO calendar_bookings 
                 (center_id, room_id, doctor_id, customer_name, area, phone, session_type_id, day, start_time, end_time, status, notes, created_by)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
              (center_id, room_id, doctor_id, customer_name, area, phone, session_type_id, day, start_time, end_time, notes, emp_id))
    conn.commit()
    conn.close()

    flash("تم تسجيل الموعد والحجز بنجاح", "success")
    return redirect(url_for("reservations.day_view", day_str=day))

@reservations_bp.route("/reservations/booking/status/<int:b_id>", methods=["POST"])
@login_required
def update_status(b_id):
    status = request.form.get("status", "pending")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE calendar_bookings SET status=? WHERE id=?", (status, b_id))
    conn.commit()
    
    cur.execute("SELECT day FROM calendar_bookings WHERE id=?", (b_id,))
    row = cur.fetchone()
    day_str = row["day"] if row else date.today().isoformat()
    conn.close()
    flash("تم تحديث حالة الحجز بنجاح", "success")
    return redirect(url_for("reservations.day_view", day_str=day_str))

@reservations_bp.route("/reservations/booking/delete/<int:b_id>", methods=["POST"])
@login_required
def delete_booking(b_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT day FROM calendar_bookings WHERE id=?", (b_id,))
    row = cur.fetchone()
    day_str = row["day"] if row else date.today().isoformat()

    cur.execute("DELETE FROM calendar_bookings WHERE id=?", (b_id,))
    conn.commit()
    conn.close()
    flash("تم حذف الحجز بنجاح", "success")
    return redirect(url_for("reservations.day_view", day_str=day_str))

# -------------------------------------------------------------
# Doctor Management
# -------------------------------------------------------------
@reservations_bp.route("/reservations/doctors", methods=["GET", "POST"])
@login_required
def doctors():
    conn = get_conn()
    cur = conn.cursor()

    if request.method == "POST":
        doc_id = request.form.get("id")
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        color = request.form.get("color", "#0d6efd")
        available_days = ",".join(request.form.getlist("available_days"))
        start_time = request.form.get("start_time", "09:00")
        end_time = request.form.get("end_time", "21:00")

        if not name:
            flash("يرجى كتابة اسم الطبيب / الأخصائي", "danger")
        else:
            if doc_id:
                cur.execute("""UPDATE doctors 
                             SET name=?, phone=?, color=?, available_days=?, start_time=?, end_time=?
                             WHERE id=?""", (name, phone, color, available_days, start_time, end_time, doc_id))
                target_id = int(doc_id)
            else:
                cur.execute("""INSERT INTO doctors (name, phone, color, available_days, start_time, end_time, active)
                             VALUES (?, ?, ?, ?, ?, ?, 1)""", (name, phone, color, available_days, start_time, end_time))
                target_id = cur.lastrowid

            # Save room assignments and shift hours if provided in form
            room_ids = request.form.getlist("room_ids")
            if room_ids:
                cur.execute("DELETE FROM doctor_rooms WHERE doctor_id=?", (target_id,))
                for rid in room_ids:
                    r_start = request.form.get(f"start_time_{rid}", "").strip() or "09:00"
                    r_end = request.form.get(f"end_time_{rid}", "").strip() or "21:00"
                    r_days = ",".join(request.form.getlist(f"days_{rid}"))
                    cur.execute("INSERT INTO doctor_rooms (doctor_id, room_id, start_time, end_time, days) VALUES (?, ?, ?, ?, ?)",
                                (target_id, int(rid), r_start, r_end, r_days))

            conn.commit()
            flash("تم حفظ بيانات الدكتور والعيادات والمواعيد بنجاح", "success")

    cur.execute("SELECT * FROM doctors ORDER BY name")
    doctors_list = [dict(d) for d in cur.fetchall()]

    cur.execute("SELECT * FROM rooms ORDER BY name")
    rooms_list = cur.fetchall()

    cur.execute("SELECT doctor_id, room_id, start_time, end_time, days FROM doctor_rooms")
    dr_rows = cur.fetchall()
    doctor_rooms = {}
    for dr in dr_rows:
        doctor_rooms.setdefault(dr["doctor_id"], []).append({
            "room_id": dr["room_id"],
            "start_time": dr["start_time"] or "09:00",
            "end_time": dr["end_time"] or "21:00",
            "days": dr["days"] or ""
        })

    conn.close()
    return render_template("doctors.html", doctors=doctors_list, rooms=rooms_list, doctor_rooms=doctor_rooms)

@reservations_bp.route("/reservations/doctors/<int:d_id>/toggle", methods=["POST"])
@login_required
def toggle_doctor(d_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE doctors SET active = CASE WHEN active=1 THEN 0 ELSE 1 END WHERE id=?", (d_id,))
    conn.commit()
    conn.close()
    flash("تم تغيير حالة تفعيل الدكتور بنجاح", "info")
    return redirect(url_for("reservations.doctors"))

@reservations_bp.route("/reservations/doctors/<int:d_id>/delete", methods=["POST"])
@login_required
def delete_doctor(d_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM doctors WHERE id=?", (d_id,))
    conn.commit()
    conn.close()
    flash("تم حذف الدكتور بنجاح", "success")
    return redirect(url_for("reservations.doctors"))

@reservations_bp.route("/reservations/doctors/<int:d_id>/rooms", methods=["POST"])
@login_required
def assign_doctor_rooms(d_id):
    room_ids = request.form.getlist("room_ids")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM doctor_rooms WHERE doctor_id=?", (d_id,))
    for rid in room_ids:
        r_start = request.form.get(f"start_time_{rid}", "").strip() or "09:00"
        r_end = request.form.get(f"end_time_{rid}", "").strip() or "21:00"
        r_days = ",".join(request.form.getlist(f"days_{rid}"))
        cur.execute("INSERT INTO doctor_rooms (doctor_id, room_id, start_time, end_time, days) VALUES (?, ?, ?, ?, ?)",
                    (d_id, int(rid), r_start, r_end, r_days))
    conn.commit()
    conn.close()
    flash("تم تحديث تعيين الغرف ومواعيدها للدكتور بنجاح", "success")
    return redirect(url_for("reservations.doctors"))

# -------------------------------------------------------------
# Room & Resource Management
# -------------------------------------------------------------
@reservations_bp.route("/reservations/rooms", methods=["GET", "POST"])
@login_required
def rooms():
    conn = get_conn()
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            cur.execute("INSERT INTO rooms (center_id, name) VALUES (1, ?)", (name,))
            conn.commit()
            flash("تم إضافة العيادة / الغرفة بنجاح", "success")

    cur.execute("SELECT * FROM rooms ORDER BY id")
    rooms_list = cur.fetchall()
    conn.close()
    return render_template("rooms.html", rooms=rooms_list)

@reservations_bp.route("/reservations/rooms/delete/<int:r_id>", methods=["POST"])
@login_required
def delete_room(r_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM rooms WHERE id=?", (r_id,))
    conn.commit()
    conn.close()
    flash("تم حذف الغرفة بنجاح", "success")
    return redirect(url_for("reservations.rooms"))

# -------------------------------------------------------------
# Session Types Management
# -------------------------------------------------------------
@reservations_bp.route("/reservations/session_types", methods=["GET", "POST"])
@login_required
def session_types():
    conn = get_conn()
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        duration = request.form.get("duration_minutes", type=int)
        if name and duration:
            cur.execute("INSERT INTO session_types (name, duration_minutes) VALUES (?, ?)", (name, duration))
            conn.commit()
            flash("تم إضافة نوع الجلسة بنجاح", "success")

    cur.execute("SELECT * FROM session_types ORDER BY duration_minutes")
    types_list = cur.fetchall()
    conn.close()
    return render_template("session_types.html", types=types_list)

@reservations_bp.route("/reservations/session_types/delete/<int:t_id>", methods=["POST"])
@login_required
def delete_session_type(t_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM session_types WHERE id=?", (t_id,))
    conn.commit()
    conn.close()
    flash("تم حذف نوع الجلسة بنجاح", "success")
    return redirect(url_for("reservations.session_types"))

# -------------------------------------------------------------
# Waitlist & Downtimes
# -------------------------------------------------------------
@reservations_bp.route("/reservations/waitlist", methods=["GET", "POST"])
@login_required
def waitlist():
    conn = get_conn()
    cur = conn.cursor()

    if request.method == "POST":
        customer_name = request.form.get("customer_name", "").strip()
        phone = request.form.get("phone", "").strip()
        session_type_id = request.form.get("session_type_id", type=int)
        day = request.form.get("day", date.today().isoformat())
        notes = request.form.get("notes", "")

        if customer_name and session_type_id:
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("""INSERT INTO waitlist (center_id, customer_name, phone, session_type_id, day, notes, created_at)
                         VALUES (1, ?, ?, ?, ?, ?, ?)""", (customer_name, phone, session_type_id, day, notes, created_at))
            conn.commit()
            flash("تم إضافة العميل لقائمة الانتظار بنجاح", "success")

    cur.execute("""SELECT w.*, st.name AS session_name 
                 FROM waitlist w 
                 JOIN session_types st ON st.id=w.session_type_id 
                 ORDER BY w.day, w.id""")
    waitlist_items = cur.fetchall()

    cur.execute("SELECT * FROM session_types ORDER BY name")
    types = cur.fetchall()

    conn.close()
    return render_template("waitlist.html", waitlist=waitlist_items, types=types)

@reservations_bp.route("/reservations/waitlist/delete/<int:w_id>", methods=["POST"])
@login_required
def delete_waitlist(w_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM waitlist WHERE id=?", (w_id,))
    conn.commit()
    conn.close()
    flash("تم حذف الطلب من قائمة الانتظار", "success")
    return redirect(url_for("reservations.waitlist"))

@reservations_bp.route("/reservations/downtimes", methods=["GET", "POST"])
@login_required
def downtimes():
    conn = get_conn()
    cur = conn.cursor()

    if request.method == "POST":
        room_id = request.form.get("room_id", type=int)
        day = request.form.get("day", date.today().isoformat())
        start_time = request.form.get("start_time", "12:00")
        end_time = request.form.get("end_time", "13:00")

        if room_id and day:
            cur.execute("""INSERT INTO downtimes (resource_type, resource_id, day, start_time, end_time)
                         VALUES ('room', ?, ?, ?, ?)""", (room_id, day, start_time, end_time))
            conn.commit()
            flash("تم حجب الوقت بنجاح", "success")

    cur.execute("""SELECT d.*, r.name AS room_name 
                 FROM downtimes d 
                 JOIN rooms r ON r.id=d.resource_id 
                 ORDER BY d.day, d.start_time""")
    downtimes_list = cur.fetchall()

    cur.execute("SELECT * FROM rooms ORDER BY name")
    rooms_list = cur.fetchall()

    conn.close()
    return render_template("downtimes.html", downtimes=downtimes_list, rooms=rooms_list)

@reservations_bp.route("/reservations/downtimes/delete/<int:d_id>", methods=["POST"])
@login_required
def delete_downtime(d_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM downtimes WHERE id=?", (d_id,))
    conn.commit()
    conn.close()
    flash("تم إلغاء حجب الوقت بنجاح", "success")
    return redirect(url_for("reservations.downtimes"))

@reservations_bp.route("/reservations/report_day")
@login_required
def report_day():
    day_str = request.args.get("day", date.today().isoformat())
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""SELECT b.*, st.name AS st_name, dc.name AS doctor_name, r.name AS room_name
                 FROM calendar_bookings b
                 JOIN session_types st ON st.id=b.session_type_id
                 LEFT JOIN rooms r ON r.id=b.room_id
                 LEFT JOIN doctors dc ON dc.id=b.doctor_id
                 WHERE b.day=? AND b.status != 'canceled'
                 ORDER BY b.start_time""", (day_str,))
    bookings = cur.fetchall()
    conn.close()

    return render_template("report_day.html", day_str=day_str, bookings=bookings)
