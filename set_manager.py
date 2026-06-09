
import os
import sqlite3
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(__file__), "verde_clinic.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Create a default manager if not exists
manager_id = 1  # You can change this to any ID you want
manager_name = "Manager"  # Change this to the manager's name
manager_password = "1234567"  # Change this to your strong password!
ph = generate_password_hash(manager_password)

# Check if the manager already exists
cur.execute("SELECT COUNT(*) FROM employees WHERE id=?", (manager_id,))
if cur.fetchone()[0] == 0:
    cur.execute(
        "INSERT INTO employees (id, name, password_hash, role) VALUES (?, ?, ?, ?)",
        (manager_id, manager_name, ph, "manager")
    )
    print(f"Manager user created successfully! ID: {manager_id}, Name: {manager_name}, Password: {manager_password}")
else:
    # Update existing manager
    cur.execute(
        "UPDATE employees SET role=?, password_hash=? WHERE id=?",
        ("manager", ph, manager_id)
    )
    print(f"Manager user updated! ID: {manager_id}, Name: {manager_name}, Password: {manager_password}")

conn.commit()
conn.close()
print("Done!")
