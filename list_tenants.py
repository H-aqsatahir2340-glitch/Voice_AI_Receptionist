# list_tenants.py
from database import SessionLocal
from models import Tenant

db = SessionLocal()
tenants = db.query(Tenant).all()
print([t.name for t in tenants])
db.close()