
from .base import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class Booking(BaseModel):
    table_name = "bookings"
    fields = [
        "id", "customer_id", "package_id", "total_sessions", "sessions_done",
        "start_date", "employee_id", "pulses_total", "pulses_used",
        "price_override", "next_session_date", "reminder_sent"
    ]

    @classmethod
    def create(cls, customer_id: int, package_id: int, total_sessions: int, 
               start_date: str, employee_id: Optional[int] = None,
               pulses_total: int = 0, price_override: Optional[int] = None):
        query = """
        INSERT INTO bookings 
        (customer_id, package_id, total_sessions, sessions_done, start_date, employee_id, pulses_total, pulses_used, price_override, next_session_date, reminder_sent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            customer_id, package_id, total_sessions, 0, start_date,
            employee_id, pulses_total, 0, price_override, None, 0
        )
        return cls.execute_query(query, params, commit=True, return_last_id=True)

    @classmethod
    def find_by_customer_id(cls, customer_id: int) -> List[Dict[str, Any]]:
        query = """
        SELECT 
            b.id, b.customer_id, b.package_id, p.name as package_name, 
            b.total_sessions, b.sessions_done, b.start_date, 
            p.price, b.price_override, b.pulses_total, b.pulses_used,
            b.next_session_date
        FROM bookings b
        LEFT JOIN packages p ON b.package_id = p.id
        WHERE b.customer_id = ?
        """
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(query, (customer_id,))
        rows = cur.fetchall()
        conn.close()
        bookings = []
        for row in rows:
            booking_dict = {
                "id": row[0],
                "customer_id": row[1],
                "package_id": row[2],
                "package_name": row[3],
                "total_sessions": row[4],
                "sessions_done": row[5],
                "start_date": row[6],
                "price": row[7],
                "package_price": row[7],
                "price_override": row[8],
                "pulses_total": row[9],
                "pulses_used": row[10],
                "next_session_date": row[11]
            }
            bookings.append(booking_dict)
        return bookings

    @classmethod
    def update_next_session_date(cls, booking_id: int, next_date: Optional[str]):
        query = "UPDATE bookings SET next_session_date = ? WHERE id = ?"
        cls.execute_query(query, (next_date, booking_id), commit=True)
        return True

    @classmethod
    def delete_with_relations(cls, booking_id: int):
        conn = get_conn()
        cur = conn.cursor()
        # Get customer_id before deleting
        cur.execute("SELECT customer_id FROM bookings WHERE id = ?", (booking_id,))
        row = cur.fetchone()
        customer_id = row[0] if row else None
        
        cur.execute("DELETE FROM sessions WHERE booking_id = ?", (booking_id,))
        cur.execute("DELETE FROM payments WHERE booking_id = ?", (booking_id,))
        cur.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
        conn.commit()
        conn.close()
        return customer_id

# We need to import get_conn from db!
from db import get_conn
