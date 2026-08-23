
from .base import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
from db import get_conn

class Expense(BaseModel):
    table_name = "expenses"
    fields = ["id", "description", "amount", "category", "date", "employee_id"]

    @classmethod
    def create(cls, description: str, amount: int, category: str, 
               date: str, employee_id: Optional[int] = None):
        query = "INSERT INTO expenses (description, amount, category, date, employee_id) VALUES (?, ?, ?, ?, ?)"
        return cls.execute_query(query, (description, amount, category, date, employee_id), commit=True, return_last_id=True)

    @classmethod
    def get_expenses_by_date_range(cls, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        query = """
        SELECT e.id, e.description, e.amount, e.category, e.date, emp.name as employee_name
        FROM expenses e
        LEFT JOIN employees emp ON e.employee_id = emp.id
        WHERE e.date BETWEEN ? AND ?
        ORDER BY e.date
        """
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(query, (start_date, end_date))
        rows = cur.fetchall()
        conn.close()
        expenses = []
        for row in rows:
            expense_dict = {
                "id": row[0],
                "description": row[1],
                "amount": row[2],
                "category": row[3],
                "date": row[4],
                "employee_name": row[5]
            }
            expenses.append(expense_dict)
        return expenses

    @classmethod
    def get_expenses_map_by_date_range(cls, start_date: str, end_date: str) -> Dict[int, int]:
        query = """
        SELECT e.employee_id, COALESCE(SUM(e.amount), 0) as total
        FROM expenses e
        WHERE e.date BETWEEN ? AND ?
        GROUP BY e.employee_id
        """
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(query, (start_date, end_date))
        rows = cur.fetchall()
        conn.close()
        expenses_map = {}
        for row in rows:
            eid = row[0]
            total = row[1]
            if eid:
                expenses_map[eid] = total
        return expenses_map

    @classmethod
    def find_all_by_date_range(cls, start_date: str, end_date: str):
        return cls.get_expenses_by_date_range(start_date, end_date)
