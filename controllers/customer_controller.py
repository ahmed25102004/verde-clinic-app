
from flask import render_template, request, redirect, url_for, flash, session
from models import Customer, Booking, Package, Session, Payment, Employee
from db import get_conn
from datetime import datetime

def customer_search():
    query_str = request.args.get("q") or request.args.get("query") or ""
    if query_str:
        customers = Customer.search(query_str)
    else:
        customers = Customer.find_all()
    # The template expects "results" variable
    return render_template("customer_search.html", results=customers, query=query_str)

def customer_detail(customer_id):
    customer = Customer.find_by_id(customer_id)
    if not customer:
        flash("العميل غير موجود", "danger")
        return redirect(url_for("customer_search"))
    
    bookings = Booking.find_by_customer_id(customer_id)
    all_packages = Package.find_all_with_category()
    employees = Employee.find_all_sorted()
    payments_map = Payment.get_payments_map()
    paid_map = Payment.get_total_paid_map()
    
    # Get sessions for each booking
    sessions_map = {}
    for booking in bookings:
        sessions_map[booking["id"]] = Session.find_by_booking_id(booking["id"])
    
    # Create compatibility variables for the template
    pkg_dict = {}
    pkg_category = {}
    for pkg in all_packages:
        pkg_dict[pkg["id"]] = pkg
        pkg_category[pkg["id"]] = pkg["category"]
    
    return render_template(
        "customer.html",
        customer=(customer["id"], customer["name"], customer["phone"], customer["note"], customer["created_at"]),
        customer_dict=customer,
        bookings=bookings,
        all_packages=all_packages,
        employees=[(e["id"], e["name"]) for e in employees],
        payments_map=payments_map,
        paid_map=paid_map,
        sessions_map=sessions_map,
        pkg_dict=pkg_dict,
        pkg_category=pkg_category
    )

def register_customer():
    package_id = request.args.get("package_id")
    if not package_id:
        flash("يرجى اختيار باكج أولاً", "danger")
        return redirect(url_for("index"))
    
    try:
        package_id = int(package_id)
    except ValueError:
        flash("باكج غير صالح", "danger")
        return redirect(url_for("index"))
    
    pkg = Package.find_by_id(package_id)
    if not pkg:
        flash("باكج غير موجود", "danger")
        return redirect(url_for("index"))
    
    employees = Employee.find_all_sorted()
    
    if request.method == "POST":
        name = request.form.get("name")
        phone = request.form.get("phone")
        note = request.form.get("note", "")
        medical_notes = request.form.get("medical_notes", "")
        allergies = request.form.get("allergies", "")
        preferences = request.form.get("preferences", "")
        medical_conditions = request.form.get("medical_conditions", "")
        employee_id = request.form.get("employee_id") or session.get("employee_id")
        first_today = request.form.get("first_today") == "on"
        pulses_total = request.form.get("pulses_total", 0)
        first_pulses = request.form.get("first_pulses", 0)
        
        if not name or not phone:
            flash("يرجى إدخال الاسم ورقم الهاتف", "danger")
            return redirect(url_for("register", package_id=package_id))
        
        try:
            employee_id = int(employee_id) if employee_id else None
            pulses_total = int(pulses_total) if pulses_total else 0
            first_pulses = int(first_pulses) if first_pulses else 0
        except ValueError:
            flash("بيانات غير صحيحة", "danger")
            return redirect(url_for("register", package_id=package_id))
        
        # Create customer
        customer_id = Customer.create(name, phone, note, medical_notes, allergies, preferences, medical_conditions)
        
        # Create booking
        start_date = datetime.now().strftime("%Y-%m-%d")
        booking_id = Booking.create(
            customer_id, package_id, pkg["sessions_count"], start_date,
            employee_id, pulses_total
        )
        
        # Create first session if needed
        if first_today:
            Session.create(
                booking_id, 1, start_date, employee_id,
                first_pulses if pulses_total > 0 else 0
            )
            # Update booking
            conn = get_conn()
            cur = conn.cursor()
            if pulses_total > 0:
                cur.execute("UPDATE bookings SET sessions_done = 1, pulses_used = ? WHERE id = ?", (first_pulses, booking_id))
            else:
                cur.execute("UPDATE bookings SET sessions_done = 1 WHERE id = ?", (booking_id,))
            conn.commit()
            conn.close()
        
        flash("تم تسجيل العميل بنجاح", "success")
        return redirect(url_for("customer", customer_id=customer_id))
    
    return render_template(
        "register.html",
        pkg=(pkg["id"], pkg["name"], pkg["price"], pkg["sessions_count"]),
        pkg_category=pkg["category"],
        employees=[(e["id"], e["name"]) for e in employees]
    )

def update_customer_medical(customer_id):
    if request.method == "POST":
        customer = Customer.find_by_id(customer_id)
        if not customer:
            flash("العميل غير موجود", "danger")
            return redirect(url_for("customer_search"))
        
        name = request.form.get("name") or customer["name"]
        phone = request.form.get("phone") or customer["phone"]
        note = request.form.get("note") or customer["note"]
        medical_notes = request.form.get("medical_notes", "")
        allergies = request.form.get("allergies", "")
        preferences = request.form.get("preferences", "")
        medical_conditions = request.form.get("medical_conditions", "")
        
        Customer.update(customer_id, name, phone, note, medical_notes, allergies, preferences, medical_conditions)
        flash("تم تحديث بيانات العميل بنجاح", "success")
    
    return redirect(url_for("customer", customer_id=customer_id))

def add_booking_to_customer(customer_id):
    if request.method == "POST":
        package_id = int(request.form.get("package_id"))
        start_date = request.form.get("start_date") or datetime.now().strftime("%Y-%m-%d")
        employee_id = int(request.form.get("employee_id")) if request.form.get("employee_id") else None
        pulses_total = int(request.form.get("pulses_total")) if request.form.get("pulses_total") else 0
        price_override = int(request.form.get("price_override")) if request.form.get("price_override") else None
        
        # Get package to know total sessions
        pkg = Package.find_by_id(package_id)
        if not pkg:
            flash("باكج غير موجود", "danger")
            return redirect(url_for("customer", customer_id=customer_id))
        
        total_sessions = pkg["sessions_count"]
        
        booking_id = Booking.create(
            customer_id, package_id, total_sessions, start_date,
            employee_id, pulses_total, price_override
        )
        
        flash("تم إضافة الحجز بنجاح", "success")
        return redirect(url_for("customer", customer_id=customer_id))
    return redirect(url_for("customer", customer_id=customer_id))

def delete_customer(customer_id):
    if request.method == "POST":
        # First delete all bookings, sessions, payments for this customer
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id FROM bookings WHERE customer_id = ?", (customer_id,))
        booking_ids = [row[0] for row in cur.fetchall()]
        
        for booking_id in booking_ids:
            cur.execute("DELETE FROM sessions WHERE booking_id = ?", (booking_id,))
            cur.execute("DELETE FROM payments WHERE booking_id = ?", (booking_id,))
            cur.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
        
        cur.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        conn.commit()
        conn.close()
        
        flash("تم حذف العميل بنجاح", "success")
    return redirect(url_for("customer_search"))
