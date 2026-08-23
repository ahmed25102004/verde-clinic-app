
import os
import sys

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import Customer, Package, Employee

print("Testing models import...")
print("✓ All models imported successfully!")

# Test db connection
from db import get_conn
conn = get_conn()
print("✓ Database connection successful!")
conn.close()

print("\nAll tests passed! The code should work correctly.")
