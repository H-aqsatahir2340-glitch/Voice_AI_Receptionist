# test_db.py
from database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    result = db.execute(text("SELECT 1"))
    print("✅ Database connected successfully!")
except Exception as e:
    print(f"❌ Error: {e}")
finally:
    db.close()