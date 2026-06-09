from functools import wraps
from flask import session, redirect, url_for, request
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("employee_id"):
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper

def manager_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("employee_id"):
            return redirect(url_for("login", next=request.path))
        if session.get("employee_role") != "manager":
            return ("Unauthorized Access", 401)
        return f(*args, **kwargs)
    return wrapper
