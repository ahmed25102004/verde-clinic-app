from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from db import get_conn
from auth import login_required, manager_required
from models import Expense, Employee, Notification

expense_bp = Blueprint('expense', __name__)

@expense_bp.route("/expenses")
@login_required
def expenses():
    expenses_list = Expense.find_all_by_date_range('1970-01-01', '2100-12-31')
    total_expenses = sum(e['amount'] for e in expenses_list)
    employees = Employee.find_all_names_sorted()
    return render_template('expenses.html', 
                         expenses=[(e['id'], e['description'], e['amount'], e['category'], e['date'], e['employee_name']) for e in expenses_list], 
                         total_expenses=total_expenses,
                         employees=employees)

@expense_bp.route("/expenses/add", methods=["POST"])
@login_required
def add_expense():
    description = request.form.get('description')
    amount = request.form.get('amount')
    category = request.form.get('category')
    employee_id = request.form.get('employee_id') or session.get('employee_id')
    
    if not description or not amount or not category:
        return redirect(url_for('expense.expenses'))
    
    try:
        amount = int(amount)
    except ValueError:
        return redirect(url_for('expense.expenses'))
    try:
        employee_id = int(employee_id or 0)
    except Exception:
        employee_id = session.get('employee_id')
    
    today = datetime.now().strftime("%Y-%m-%d")
    Expense.create(description, amount, category, today, employee_id)
    if amount >= 500:
        Notification.create(f"مصروف عالي: {description} بمبلغ {amount} ج.م", "warning")
    return redirect(url_for('expense.expenses'))

@expense_bp.route("/expenses/delete/<int:expense_id>")
@manager_required
def delete_expense(expense_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()
    flash("تم حذف المصروف بنجاح", "success")
    return redirect(url_for('expense.expenses'))
