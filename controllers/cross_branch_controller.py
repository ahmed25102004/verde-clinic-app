import os
import requests
from flask import Blueprint, request, jsonify, redirect, url_for, flash, session
from db import get_conn
from auth import login_required
from datetime import datetime

cross_branch_bp = Blueprint("cross_branch", __name__)

def normalize_phone_str(p):
    if not p: return ""
    p = str(p).translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
    return "".join(c for c in p if c.isdigit())

@cross_branch_bp.route("/api/remote_search", methods=["GET", "OPTIONS"])
def remote_search():
    if request.method == "OPTIONS":
        resp = jsonify({})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return resp, 200

    q = request.args.get("q", "").strip()
    if not q:
        resp = jsonify({"status": "success", "results": []})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp
        
    conn = get_conn()
    cur = conn.cursor()
    
    q_norm = q.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')).strip()
    digits_only = "".join(c for c in q_norm if c.isdigit())
    stripped_digits = digits_only.lstrip('0') if digits_only.startswith('0') else digits_only
    
    cur.execute("SELECT c.id, c.name, c.phone, c.gender, c.note FROM customers c")
    all_customers = cur.fetchall()
    
    matched_customers = []
    for c in all_customers:
        c_id, c_name, c_phone, c_gender, c_note = c[0], c[1] or "", c[2] or "", c[3], c[4]
        c_phone_norm = normalize_phone_str(c_phone)
        c_phone_stripped = c_phone_norm.lstrip('0') if c_phone_norm.startswith('0') else c_phone_norm
        
        is_match = False
        if q_norm.lower() in c_name.lower():
            is_match = True
        elif q_norm in c_phone:
            is_match = True
        elif digits_only and len(digits_only) >= 3:
            if digits_only in c_phone_norm or c_phone_norm in digits_only:
                is_match = True
            elif stripped_digits and len(stripped_digits) >= 3 and (stripped_digits in c_phone_stripped or c_phone_stripped in stripped_digits):
                is_match = True

        if is_match:
            matched_customers.append(c)
            if len(matched_customers) >= 20:
                break

    results = []
    for c in matched_customers:
        cust_id = c[0]
        cur.execute("""
            SELECT b.id, b.package_id, p.name, p.category, b.total_sessions, b.sessions_done, 
                   COALESCE(b.price_override, p.price) as price, b.pulses_total, b.pulses_used, b.start_date
            FROM bookings b
            JOIN packages p ON p.id = b.package_id
            WHERE b.customer_id = ?
        """, (cust_id,))
        b_rows = cur.fetchall()
        
        bookings_list = []
        for b in b_rows:
            bookings_list.append({
                "booking_id": b[0],
                "package_id": b[1],
                "package_name": b[2],
                "category": b[3],
                "total_sessions": b[4],
                "sessions_done": b[5],
                "price": b[6],
                "pulses_total": b[7],
                "pulses_used": b[8],
                "start_date": b[9]
            })
            
        results.append({
            "customer_id": c[0],
            "name": c[1],
            "phone": c[2],
            "gender": c[3] or "أنثى",
            "note": c[4] or "",
            "bookings": bookings_list
        })
        
    conn.close()
    
    this_port = str(os.getenv("PORT", "8090"))
    branch_default = "فرع المسلة" if "8090" in this_port else "فرع العبودي"
    
    resp = jsonify({
        "status": "success",
        "branch_name": os.getenv("THIS_BRANCH_NAME", branch_default),
        "results": results
    })
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

@cross_branch_bp.route("/api/search_other_branch", methods=["GET"])
@login_required
def search_other_branch():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"status": "error", "message": "يرجى كتابة اسم أو رقم هاتف للبحث"})

    # Check explicit env vars first
    target_container = os.getenv("OTHER_CONTAINER")
    target_port = os.getenv("OTHER_PORT")
    other_branch_name = os.getenv("OTHER_BRANCH_NAME")

    if not target_container or not target_port:
        import socket
        hostname = socket.gethostname().lower()
        this_port = str(os.getenv("PORT", "8090"))
        
        if "aboudi" in hostname or "8091" in this_port:
            target_container = "la_verde_almasala_app"
            target_port = "8090"
            other_branch_name = other_branch_name or "فرع المسلة"
        else:
            target_container = "la_verde_alaboudi_app"
            target_port = "8091"
            other_branch_name = other_branch_name or "فرع العبودي"
    custom_url = os.getenv("OTHER_BRANCH_URL", "").strip()

    candidate_urls = []
    if custom_url:
        candidate_urls.append(custom_url.rstrip('/'))
        
    candidate_urls.extend([
        f"http://{target_container}:5007",
        f"http://186.240.152.148:{target_port}",
        f"http://172.17.0.1:{target_port}",
        f"http://host.docker.internal:{target_port}",
        f"http://127.0.0.1:{target_port}"
    ])

    errors = []
    for base_url in candidate_urls:
        try:
            url = f"{base_url}/api/remote_search?q={requests.utils.quote(q)}"
            resp = requests.get(url, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                data["other_branch_name"] = other_branch_name
                return jsonify(data)
            else:
                errors.append(f"{base_url} (HTTP {resp.status_code})")
        except Exception as e:
            errors.append(f"{base_url} ({e})")
            continue
            
    err_msg = " | ".join(errors[:2]) if errors else "تعذر الوصول"
    return jsonify({"status": "error", "message": f"تعذر الاتصال بـ {other_branch_name}: {err_msg}"})

@cross_branch_bp.route("/api/import_remote_customer", methods=["POST"])
@login_required
def import_remote_customer():
    data = request.json or {}
    phone = data.get("phone", "").strip()
    name = data.get("name", "").strip()
    gender = data.get("gender", "أنثى")
    note = data.get("note", "")
    
    pkg_name = data.get("package_name", "باكدج مشترك بين الفروع")
    category = data.get("category", "cross_branch")
    total_sessions = int(data.get("total_sessions", 1))
    sessions_done = int(data.get("sessions_done", 0))
    price = int(data.get("price", 0))
    pulses_total = int(data.get("pulses_total", 0))
    pulses_used = int(data.get("pulses_used", 0))
    remote_booking_id = data.get("booking_id")
    remote_branch_name = data.get("branch_name", os.getenv("OTHER_BRANCH_NAME", "الفرع الآخر"))

    if not phone or not name:
        return jsonify({"status": "error", "message": "بيانات العميل غير مكتملة"})

    conn = get_conn()
    cur = conn.cursor()
    
    # 1. Check or Create Customer
    cur.execute("SELECT id FROM customers WHERE phone = ?", (phone,))
    c_row = cur.fetchone()
    if c_row:
        cust_id = c_row[0]
    else:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("INSERT INTO customers (name, phone, gender, note, created_at) VALUES (?,?,?,?,?)",
                    (name, phone, gender, f"مشترك من {remote_branch_name} | {note}".strip(), created_at))
        cust_id = cur.lastrowid

    # 2. Check or Create Matching Package
    cur.execute("SELECT id FROM packages WHERE name = ? AND category = ?", (pkg_name, category))
    pkg_row = cur.fetchone()
    if pkg_row:
        pkg_id = pkg_row[0]
    else:
        cur.execute("INSERT INTO packages (category, name, sessions_count, price, bonus) VALUES (?,?,?,?,?)",
                    (category, pkg_name, total_sessions, price, f"من {remote_branch_name}"))
        pkg_id = cur.lastrowid

    # 3. Create Local Booking
    today_str = datetime.now().strftime("%Y-%m-%d")
    emp_id = session.get("employee_id")
    
    cur.execute("""
        INSERT INTO bookings (customer_id, package_id, total_sessions, sessions_done, start_date, employee_id,
                              pulses_total, pulses_used, price_override, remote_booking_id, remote_branch_name)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (cust_id, pkg_id, total_sessions, sessions_done, today_str, emp_id,
          pulses_total, pulses_used, price, remote_booking_id, remote_branch_name))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        "status": "success",
        "customer_id": cust_id,
        "redirect_url": f"/customer/{cust_id}"
    })

@cross_branch_bp.route("/api/sync_remote_session", methods=["POST"])
def sync_remote_session():
    data = request.json or {}
    remote_booking_id = data.get("remote_booking_id")
    sessions_done = data.get("sessions_done")
    pulses_used = data.get("pulses_used", 0)
    
    if not remote_booking_id or sessions_done is None:
        return jsonify({"status": "error", "message": "معرف الحجز غير محدد"})
        
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE bookings 
        SET sessions_done = ?, pulses_used = MAX(pulses_used, ?)
        WHERE id = ?
    """, (sessions_done, pulses_used, remote_booking_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})
