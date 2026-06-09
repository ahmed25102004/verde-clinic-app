
from .base import BaseModel
from typing import List, Dict, Any, Optional

class Notification(BaseModel):
    table_name = "notifications"
    fields = ["id", "message", "type", "is_read", "created_at"]

    @classmethod
    def create(cls, message: str, type: str = "info"):
        query = "INSERT INTO notifications (message, type, is_read, created_at) VALUES (?, ?, 0, CURRENT_TIMESTAMP)"
        return cls.execute_query(query, (message, type), commit=True, return_last_id=True)

    @classmethod
    def find_unread(cls) -> List[Dict[str, Any]]:
        query = "SELECT * FROM notifications WHERE is_read = 0 ORDER BY created_at DESC"
        rows = cls.execute_query(query, fetch=True)
        return [cls._row_to_dict(row) for row in rows] if rows else []

    @classmethod
    def mark_as_read(cls, id: int):
        query = "UPDATE notifications SET is_read = 1 WHERE id = ?"
        cls.execute_query(query, (id,), commit=True)
        return True
