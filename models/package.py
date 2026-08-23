
from .base import BaseModel
from typing import List, Dict, Any

class Package(BaseModel):
    table_name = "packages"
    fields = ["id", "category", "name", "sessions_count", "price", "bonus"]

    @classmethod
    def find_by_category(cls, category: str) -> List[Dict[str, Any]]:
        query = "SELECT * FROM packages WHERE category = ?"
        rows = cls.execute_query(query, (category,), fetch=True)
        return [cls._row_to_dict(row) for row in rows] if rows else []

    @classmethod
    def find_all_with_category(cls) -> List[Dict[str, Any]]:
        query = "SELECT id, category, name, sessions_count, price, bonus FROM packages"
        rows = cls.execute_query(query, fetch=True)
        packages = []
        for row in rows:
            package_dict = {
                "id": row[0],
                "category": row[1],
                "name": row[2],
                "sessions_count": row[3],
                "price": row[4],
                "bonus": row[5]
            }
            packages.append(package_dict)
        return packages
