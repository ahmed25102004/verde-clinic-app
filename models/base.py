
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import get_conn
from typing import List, Optional, Dict, Any

class BaseModel:
    table_name: str = None
    fields: List[str] = []

    @classmethod
    def execute_query(cls, query: str, params: tuple = (), fetch: bool = False, commit: bool = False, return_last_id: bool = False):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(query, params)
        result = None
        last_id = None
        if fetch:
            result = cur.fetchall()
        if commit:
            conn.commit()
            if return_last_id:
                last_id = cur.lastrowid
        conn.close()
        if return_last_id:
            return last_id
        return result

    @classmethod
    def find_all(cls) -> List[Dict[str, Any]]:
        query = f"SELECT * FROM {cls.table_name}"
        rows = cls.execute_query(query, fetch=True)
        return [cls._row_to_dict(row) for row in rows] if rows else []

    @classmethod
    def find_by_id(cls, id: int) -> Optional[Dict[str, Any]]:
        query = f"SELECT * FROM {cls.table_name} WHERE id = ?"
        rows = cls.execute_query(query, (id,), fetch=True)
        return cls._row_to_dict(rows[0]) if rows else None

    @classmethod
    def delete(cls, id: int) -> bool:
        query = f"DELETE FROM {cls.table_name} WHERE id = ?"
        cls.execute_query(query, (id,), commit=True)
        return True

    @classmethod
    def _row_to_dict(cls, row: tuple) -> Dict[str, Any]:
        if not row:
            return {}
        return {cls.fields[i]: row[i] for i in range(min(len(row), len(cls.fields)))}
