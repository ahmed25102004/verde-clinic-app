
from .base import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class Customer(BaseModel):
    table_name = "customers"
    fields = ["id", "name", "phone", "note", "created_at", "medical_notes", "allergies", "preferences", "medical_conditions"]

    @classmethod
    def create(cls, name: str, phone: str, note: str = "", medical_notes: str = "", allergies: str = "", preferences: str = "", medical_conditions: str = ""):
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = "INSERT INTO customers (name, phone, note, created_at, medical_notes, allergies, preferences, medical_conditions) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        return cls.execute_query(query, (name, phone, note, created_at, medical_notes, allergies, preferences, medical_conditions), commit=True, return_last_id=True)

    @classmethod
    def search(cls, query_str: str) -> List[Dict[str, Any]]:
        query = "SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ?"
        search_param = f"%{query_str}%"
        rows = cls.execute_query(query, (search_param, search_param), fetch=True)
        return [cls._row_to_dict(row) for row in rows] if rows else []

    @classmethod
    def find_by_phone(cls, phone: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM customers WHERE phone = ?"
        rows = cls.execute_query(query, (phone,), fetch=True)
        return cls._row_to_dict(rows[0]) if rows else None

    @classmethod
    def update(cls, id: int, name: str, phone: str, note: str, medical_notes: str = "", allergies: str = "", preferences: str = "", medical_conditions: str = ""):
        query = "UPDATE customers SET name = ?, phone = ?, note = ?, medical_notes = ?, allergies = ?, preferences = ?, medical_conditions = ? WHERE id = ?"
        cls.execute_query(query, (name, phone, note, medical_notes, allergies, preferences, medical_conditions, id), commit=True)
        return True
