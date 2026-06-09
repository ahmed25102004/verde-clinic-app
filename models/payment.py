
from .base import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
from db import get_conn

class Payment(BaseModel):
    table_name = "payments"
    fields = ["id", "booking_id", "amount", "method", "date", "employee_id"]

    @classmethod
    def create(cls, booking_id: int, amount: int, method: str, 
               date: str, employee_id: Optional[int] = None):
        query = "INSERT INTO payments (booking_id, amount, method, date, employee_id) VALUES (?, ?, ?, ?, ?)"
        return cls.execute_query(query, (booking_id, amount, method, date, employee_id), commit=True, return_last_id=True)

    @classmethod
    def get_total_paid_by_booking(cls, booking_id: int) -> int:
        query = "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE booking_id = ?"
        row = cls.execute_query(query, (booking_id,), fetch=True)
        return row[0][0] if row else 0

    @classmethod
    def get_payments_by_booking(cls, booking_id: int) -> List[Dict[str, Any]]:
        query = "SELECT * FROM payments WHERE booking_id = ? ORDER BY date"
        rows = cls.execute_query(query, (booking_id,), fetch=True)
        return [cls._row_to_dict(row) for row in rows] if rows else []

    @classmethod
    def get_total_paid_map(cls) -> Dict[int, int]:
        query = "SELECT booking_id, SUM(amount) FROM payments GROUP BY booking_id"
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        conn.close()
        total_paid_map = {}
        for row in rows:
            total_paid_map[row[0]] = row[1]
        return total_paid_map

    @classmethod
    def get_payments_map(cls) -> Dict[int, List[tuple]]:
        query = "SELECT p.booking_id, p.amount, p.method, p.date, e.name FROM payments p LEFT JOIN employees e ON p.employee_id = e.id ORDER BY p.booking_id, p.date"
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        conn.close()
        payments_map = {}
        for row in rows:
            booking_id = row[0]
            payment_tuple = (row[1], row[2], row[3], row[4])  # (amount, method, date, employee name)
            if booking_id not in payments_map:
                payments_map[booking_id] = []
            payments_map[booking_id].append(payment_tuple)
        return payments_map
