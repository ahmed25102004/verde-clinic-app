from functools import wraps
from flask import session, redirect, url_for, request

def get_login_url():
    try:
        return url_for("employee.login", next=request.path)
    except Exception:
        return url_for("login", next=request.path)

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("employee_id"):
            return redirect(get_login_url())
        return f(*args, **kwargs)
    return wrapper

def manager_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("employee_id"):
            return redirect(get_login_url())
        if session.get("employee_role") != "manager":
            return ("Unauthorized Access", 401)
        return f(*args, **kwargs)
    return wrapper

