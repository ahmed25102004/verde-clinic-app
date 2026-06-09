
from .base import BaseModel
from typing import Optional, Dict, Any

class WhatsAppSettings(BaseModel):
    table_name = "whatsapp_settings"
    fields = ["id", "instance_id", "api_token", "sender_phone", "is_active", "created_at"]

    @classmethod
    def get_settings(cls) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM whatsapp_settings ORDER BY id DESC LIMIT 1"
        rows = cls.execute_query(query, fetch=True)
        if rows:
            return cls._row_to_dict(rows[0])
        return None

    @classmethod
    def update_settings(cls, instance_id: str, api_token: str, sender_phone: Optional[str] = None, is_active: int = 1):
        current = cls.get_settings()
        if current:
            query = """
            UPDATE whatsapp_settings 
            SET instance_id = ?, api_token = ?, sender_phone = ?, is_active = ?
            WHERE id = ?
            """
            cls.execute_query(query, (instance_id, api_token, sender_phone, is_active, current["id"]), commit=True)
        else:
            query = """
            INSERT INTO whatsapp_settings (instance_id, api_token, sender_phone, is_active, created_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """
            cls.execute_query(query, (instance_id, api_token, sender_phone, is_active), commit=True)
        return True
