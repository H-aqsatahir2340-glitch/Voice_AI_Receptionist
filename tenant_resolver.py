# tenant_resolver.py
from sqlalchemy.orm import Session
from models import Tenant, Configs
import secrets

def get_tenant_by_phone(db: Session, phone_number: str):
    """Resolve tenant by Twilio phone number"""
    return db.query(Tenant).filter(Tenant.phone_number == phone_number).first()

def get_tenant_by_api_key(db: Session, api_key: str):
    """Resolve tenant by API key"""
    return db.query(Tenant).filter(Tenant.api_key == api_key).first()

def get_tenant_by_id(db: Session, tenant_id: int):
    """Resolve tenant by ID"""
    return db.query(Tenant).filter(Tenant.id == tenant_id).first()

def create_tenant(db: Session, name: str, vertical: str, phone_number: str, api_key: str = None):
    """Create a new tenant with default config"""
    if api_key is None:
        api_key = secrets.token_urlsafe(32)
    
    # Create tenant (without config column)
    tenant = Tenant(
        name=name,
        vertical=vertical,
        phone_number=phone_number,
        api_key=api_key,
        status="draft"
    )
    
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    
    # Create default config
    default_config = Configs(
        tenant_id=tenant.id,
        hours={
            "monday": "9am-6pm",
            "tuesday": "9am-6pm",
            "wednesday": "9am-6pm",
            "thursday": "9am-6pm",
            "friday": "9am-6pm",
            "saturday": "10am-4pm",
            "sunday": "closed"
        },
        services=["General Services"],
        booking_rules={"advance_notice": 24},
        persona="You are a friendly AI receptionist."
    )
    db.add(default_config)
    db.commit()
    
    return tenant