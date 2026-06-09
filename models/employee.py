
from .base import BaseModel
from typing import List, Dict, Any, Optional

class Employee(BaseModel):
    table_name = "employees"
    fields = ["id", "name", "password_hash", "role"]

    @classmethod
    def create(cls, name: str, password_hash: Optional[str] = None, role: Optional[str] = None):
        query = "INSERT INTO employees (name, password_hash, role) VALUES (?, ?, ?)"
        return cls.execute_query(query, (name, password_hash, role), commit=True, return_last_id=True)

    @classmethod
    def find_all_sorted(cls) -> List[Dict[str, Any]]:
        query = "SELECT * FROM employees ORDER BY name"
        rows = cls.execute_query(query, fetch=True)
        return [cls._row_to_dict(row) for row in rows] if rows else []

    @classmethod
    def find_all_names_sorted(cls):
        return cls.find_all_sorted()
