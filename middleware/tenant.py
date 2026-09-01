# middleware/tenant.py
from database import SessionLocal
from models import Tenant

def resolve_tenant_from_api_key(api_key: str):
    """Resolve tenant from API key"""
    db = SessionLocal()
    tenant = db.query(Tenant).filter(Tenant.api_key == api_key).first()
    db.close()
    return tenant

def resolve_tenant_from_phone(phone_number: str):
    """Resolve tenant from Twilio phone number"""
    db = SessionLocal()
    tenant = db.query(Tenant).filter(Tenant.phone_number == phone_number).first()
    db.close()
    return tenant