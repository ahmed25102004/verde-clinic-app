
from .base import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
from db import get_conn

class Session(BaseModel):
    table_name = "sessions"
    fields = [
        "id", "booking_id", "session_number", "date", 
        "employee_id", "pulses_used", "note"
    ]

    @classmethod
    def create(cls, booking_id: int, session_number: int, 
               date: str, employee_id: Optional[int] = None,
               pulses_used: int = 0, note: str = ""):
        query = """
        INSERT INTO sessions 
        (booking_id, session_number, date, employee_id, pulses_used, note)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        return cls.execute_query(
            query, (booking_id, session_number, date, employee_id, pulses_used, note),
            commit=True, return_last_id=True
        )

    @classmethod
    def find_by_booking_id(cls, booking_id: int) -> List[Dict[str, Any]]:
        query = """
        SELECT s.id, s.booking_id, s.session_number, s.date, s.employee_id, s.pulses_used, s.note, e.name as employee_name
        FROM sessions s
        LEFT JOIN employees e ON s.employee_id = e.id
        WHERE s.booking_id = ?
        ORDER BY s.session_number
        """
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(query, (booking_id,))
        rows = cur.fetchall()
        conn.close()
        sessions = []
        for row in rows:
            session_dict = {
                "id": row[0],
                "booking_id": row[1],
                "session_number": row[2],
                "date": row[3],
                "employee_id": row[4],
                "pulses_used": row[5],
                "note": row[6],
                "employee_name": row[7]
            }
            sessions.append(session_dict)
        return sessions

    @classmethod
    def delete_and_update_booking(cls, session_id: int):
        conn = get_conn()
        cur = conn.cursor()
        # Get session info: booking_id and pulses_used
        cur.execute("SELECT booking_id, pulses_used FROM sessions WHERE id = ?", (session_id,))
        session_info = cur.fetchone()
        if not session_info:
            conn.close()
            return None
        booking_id, pulses_to_subtract = session_info
        
        # Delete the session
        cur.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        
        # Subtract pulses from booking and decrease sessions_done
        cur.execute("""
        UPDATE bookings 
        SET sessions_done = sessions_done - 1,
            pulses_used = pulses_used - ?
        WHERE id = ?
        """, (pulses_to_subtract, booking_id))
        
        # Re-number the remaining sessions
        cur.execute("SELECT id FROM sessions WHERE booking_id = ? ORDER BY session_number", (booking_id,))
        remaining_sessions = cur.fetchall()
        for i, (sess_id,) in enumerate(remaining_sessions, 1):
            cur.execute("UPDATE sessions SET session_number = ? WHERE id = ?", (i, sess_id))
        
        conn.commit()
        conn.close()
        return booking_id

    @classmethod
    def update_note(cls, id: int, note: str):
        query = "UPDATE sessions SET note = ? WHERE id = ?"
        cls.execute_query(query, (note, id), commit=True)
        return True
