# api/auth.py
from fastapi import HTTPException, Header
from database import SessionLocal
from models import Tenant

async def verify_api_key(x_api_key: str = Header(...)):
    """Verify API key and return tenant"""
    db = SessionLocal()
    tenant = db.query(Tenant).filter(Tenant.api_key == x_api_key).first()
    db.close()
    
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return tenant