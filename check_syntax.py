
import ast
import sys

try:
    with open('app.py', 'r', encoding='utf-8') as f:
        source = f.read()
    ast.parse(source, filename='app.py')
    print("✅ No syntax errors found!")
except SyntaxError as e:
    print(f"❌ Syntax error at line {e.lineno}, column {e.offset}:")
    print(f"   {e.text}")
    print(f"   {' ' * (e.offset - 1)}^")
    print(f"   {e.msg}")
