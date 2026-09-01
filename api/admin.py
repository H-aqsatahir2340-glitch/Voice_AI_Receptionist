# api/admin.py
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional, List
from database import get_db
from models import (
    Tenant, Configs, KnowledgeSource, Document, 
    Conversation, Booking, Lead, Message
)
from tenant_resolver import create_tenant
from ingestion import chunk_source, store_chunks_in_qdrant
from qdrant_utils import get_qdrant_client
import shutil
import os
import json

router = APIRouter(prefix="/api/admin", tags=["Admin"])


# ──────────────────────────────────────────────
# 1. LIST TENANTS (GET)
# ──────────────────────────────────────────────
@router.get("/tenants")
async def list_tenants(db: Session = Depends(get_db)):
    """List all tenants"""
    tenants = db.query(Tenant).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "vertical": t.vertical,
            "status": t.status,
            "api_key": t.api_key,
            "phone_number": t.phone_number
        }
        for t in tenants
    ]
@router.post("/tenants/{tenant_id}/ingest")
async def ingest_file(
    tenant_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and ingest a file for a tenant"""
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Save file temporarily
    file_path = f"temp_{file.filename}"
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Chunk the file
    from ingestion import chunk_source, store_chunks_in_qdrant
    from qdrant_utils import get_qdrant_client
    
    chunks = chunk_source(file_path)
    os.remove(file_path)
    
    if chunks:
        client = get_qdrant_client()
        store_chunks_in_qdrant(
            client=client,
            collection_name="knowledge",
            tenant_id=tenant_id,
            chunks=chunks,
            source_name=file.filename
        )
        
        # Save to PostgreSQL
        source = KnowledgeSource(
            tenant_id=tenant_id,
            type="file",
            name=file.filename,
            status="completed"
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        
        for chunk in chunks:
            doc = Document(
                source_id=source.id,
                tenant_id=tenant_id,
                chunk_text=chunk,
                meta={"source": file.filename}
            )
            db.add(doc)
        db.commit()
        
        return {
            "message": f"Stored {len(chunks)} chunks for tenant {tenant_id}",
            "chunks": len(chunks)
        }
    else:
        return {"message": "No text extracted from file", "chunks": 0}

# ──────────────────────────────────────────────
# 2. CREATE TENANT (POST)
# ──────────────────────────────────────────────
@router.post("/tenants")
async def create_tenant_api(
    name: str,
    vertical: str,
    phone_number: str,
    db: Session = Depends(get_db)
):
    """Create a new tenant with default config"""
    
    tenant = create_tenant(
        db=db,
        name=name,
        vertical=vertical,
        phone_number=phone_number
    )
    
    # Check if config already exists
    existing_config = db.query(Configs).filter(Configs.tenant_id == tenant.id).first()
    
    if not existing_config:
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
    
    return {
        "id": tenant.id,
        "name": tenant.name,
        "api_key": tenant.api_key,
        "status": tenant.status
    }


# ──────────────────────────────────────────────
# 3. BATCH UPLOAD KNOWLEDGE (POST)
# ──────────────────────────────────────────────
# api/admin.py

@router.post("/tenants/{tenant_id}/ingest-batch")
async def ingest_batch(
    tenant_id: int,
    files: List[UploadFile] = File([]),
    urls: str = Form(""),
    db: Session = Depends(get_db)
):
    """Ingest multiple files and URLs at once"""
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    results = []
    total_chunks = 0
    total_sources = 0
    
    # ─── Process each file ───
    for file in files:
        file_path = f"temp_{file.filename}"
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        chunks = chunk_source(file_path)
        os.remove(file_path)
        
        if chunks:
            # 1. Store in Qdrant
            client = get_qdrant_client()
            store_chunks_in_qdrant(
                client=client,
                collection_name="knowledge",
                tenant_id=tenant_id,
                chunks=chunks,
                source_name=file.filename
            )
            
            # ──────────────────────────────────────────────
            # 2. SAVE TO POSTGRESQL (ADD THIS)
            # ──────────────────────────────────────────────
            source = KnowledgeSource(
                tenant_id=tenant_id,
                type="file",
                name=file.filename,
                status="completed"
            )
            db.add(source)
            db.commit()
            db.refresh(source)
            
            for chunk in chunks:
                doc = Document(
                    source_id=source.id,
                    tenant_id=tenant_id,
                    chunk_text=chunk,
                    meta={"source": file.filename}
                )
                db.add(doc)
            db.commit()
            # ──────────────────────────────────────────────
            
            total_chunks += len(chunks)
            total_sources += 1
            results.append({
                "name": file.filename,
                "chunks": len(chunks),
                "status": "success"
            })
        else:
            results.append({
                "name": file.filename,
                "chunks": 0,
                "status": "failed",
                "error": "No text extracted"
            })
    
    # ─── Process URLs ───
    if urls:
        url_list = [u.strip() for u in urls.split('\n') if u.strip()]
        for url in url_list:
            chunks = chunk_source(url)
            if chunks:
                client = get_qdrant_client()
                store_chunks_in_qdrant(
                    client=client,
                    collection_name="knowledge",
                    tenant_id=tenant_id,
                    chunks=chunks,
                    source_name=url
                )
                
                # ──────────────────────────────────────────────
                # 2. SAVE TO POSTGRESQL (ADD THIS FOR URLs)
                # ──────────────────────────────────────────────
                source = KnowledgeSource(
                    tenant_id=tenant_id,
                    type="url",
                    name=url,
                    status="completed"
                )
                db.add(source)
                db.commit()
                db.refresh(source)
                
                for chunk in chunks:
                    doc = Document(
                        source_id=source.id,
                        tenant_id=tenant_id,
                        chunk_text=chunk,
                        meta={"source": url}
                    )
                    db.add(doc)
                db.commit()
                # ──────────────────────────────────────────────
                
                total_chunks += len(chunks)
                total_sources += 1
                results.append({
                    "name": url,
                    "chunks": len(chunks),
                    "status": "success"
                })
            else:
                results.append({
                    "name": url,
                    "chunks": 0,
                    "status": "failed",
                    "error": "No text extracted"
                })
    
    return {
        "message": f"Processed {total_sources} sources",
        "total_chunks": total_chunks,
        "results": results
    }

# ──────────────────────────────────────────────
# 4. LIST KNOWLEDGE SOURCES (GET)
# ──────────────────────────────────────────────
@router.get("/tenants/{tenant_id}/knowledge")
async def list_knowledge(
    tenant_id: int,
    db: Session = Depends(get_db)
):
    """List all knowledge sources for a tenant"""
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    sources = db.query(KnowledgeSource).filter(
        KnowledgeSource.tenant_id == tenant_id
    ).order_by(KnowledgeSource.created_at.desc()).all()
    
    result = []
    for source in sources:
        documents = db.query(Document).filter(
            Document.source_id == source.id
        ).all()
        result.append({
            "id": source.id,
            "name": source.name,
            "type": source.type,
            "status": source.status,
            "chunks": len(documents),
            "created_at": source.created_at.isoformat() if source.created_at else None,
            "documents": [
                {
                    "id": doc.id,
                    "text": doc.chunk_text[:200] + "..." if len(doc.chunk_text) > 200 else doc.chunk_text
                }
                for doc in documents[:5]
            ]
        })
    
    return {
        "tenant_id": tenant_id,
        "tenant_name": tenant.name,
        "total_sources": len(result),
        "sources": result
    }


# ──────────────────────────────────────────────
# 5. DELETE SPECIFIC KNOWLEDGE SOURCE (DELETE)
# ──────────────────────────────────────────────
@router.delete("/tenants/{tenant_id}/knowledge/{source_id}")
async def delete_knowledge_source(
    tenant_id: int,
    source_id: int,
    db: Session = Depends(get_db)
):
    """Delete a specific knowledge source and its chunks"""
    
    source = db.query(KnowledgeSource).filter(
        KnowledgeSource.id == source_id,
        KnowledgeSource.tenant_id == tenant_id
    ).first()
    
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found")
    
    try:
        from qdrant_client.http import models
        
        client = get_qdrant_client()
        
        client.delete(
            collection_name="knowledge",
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="tenant_id",
                            match=models.MatchValue(value=tenant_id)
                        ),
                        models.FieldCondition(
                            key="source",
                            match=models.MatchValue(value=source.name)
                        )
                    ]
                )
            )
        )
        
        db.query(Document).filter(Document.source_id == source_id).delete()
        db.delete(source)
        db.commit()
        
        return {
            "message": f"Deleted knowledge source: {source.name}",
            "source_id": source_id
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting: {str(e)}")


# ──────────────────────────────────────────────
# 6. DELETE ALL KNOWLEDGE (DELETE)
# ──────────────────────────────────────────────
@router.delete("/tenants/{tenant_id}/knowledge")
async def delete_all_knowledge(
    tenant_id: int,
    db: Session = Depends(get_db)
):
    """Delete all knowledge chunks for a tenant"""
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    try:
        from qdrant_client.http import models
        
        client = get_qdrant_client()
        
        client.delete(
            collection_name="knowledge",
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="tenant_id",
                            match=models.MatchValue(value=tenant_id)
                        )
                    ]
                )
            )
        )
        
        sources = db.query(KnowledgeSource).filter(KnowledgeSource.tenant_id == tenant_id).all()
        for source in sources:
            db.query(Document).filter(Document.source_id == source.id).delete()
            db.delete(source)
        db.commit()
        
        return {
            "message": f"Deleted all knowledge for tenant {tenant_id}",
            "tenant_id": tenant_id,
            "tenant_name": tenant.name
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting: {str(e)}")


# ──────────────────────────────────────────────
# 7. UPDATE CONFIG (PUT)
# ──────────────────────────────────────────────
@router.put("/tenants/{tenant_id}/config")
async def update_config(
    tenant_id: int,
    config_data: dict,
    db: Session = Depends(get_db)
):
    """Update tenant configuration"""
    
    config = db.query(Configs).filter(Configs.tenant_id == tenant_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    if "hours" in config_data:
        config.hours = config_data["hours"]
    if "services" in config_data:
        config.services = config_data["services"]
    if "booking_rules" in config_data:
        config.booking_rules = config_data["booking_rules"]
    if "persona" in config_data:
        config.persona = config_data["persona"]
    if "voice" in config_data:
        config.voice = config_data["voice"]
    
    db.commit()
    
    return {"message": "Config updated", "config": {
        "hours": config.hours,
        "services": config.services,
        "booking_rules": config.booking_rules
    }}


# ──────────────────────────────────────────────
# 8. GET CONFIG (GET)
# ──────────────────────────────────────────────
@router.get("/tenants/{tenant_id}/config")
async def get_config(
    tenant_id: int,
    db: Session = Depends(get_db)
):
    """Get tenant configuration"""
    
    config = db.query(Configs).filter(Configs.tenant_id == tenant_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    return {
        "hours": config.hours,
        "services": config.services,
        "booking_rules": config.booking_rules,
        "persona": config.persona,
        "voice": config.voice
    }


# ──────────────────────────────────────────────
# 9. PUBLISH TENANT (POST)
# ──────────────────────────────────────────────
@router.post("/tenants/{tenant_id}/publish")
async def publish_tenant(
    tenant_id: int,
    db: Session = Depends(get_db)
):
    """Publish tenant agent"""
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    tenant.status = "published"
    db.commit()
    
    return {"message": f"Tenant {tenant.name} published successfully"}


# ──────────────────────────────────────────────
# 10. CONVERSATIONS (GET)
# ──────────────────────────────────────────────
@router.get("/tenants/{tenant_id}/conversations")
async def get_conversations(
    tenant_id: int,
    db: Session = Depends(get_db)
):
    """Get all conversations for a tenant"""
    conversations = db.query(Conversation).filter(
        Conversation.tenant_id == tenant_id
    ).order_by(Conversation.started_at.desc()).all()
    
    return [
        {
            "id": c.id,
            "channel": c.channel,
            "started_at": c.started_at,
            "ended_at": c.ended_at,
            "message_count": len(c.messages)
        }
        for c in conversations
    ]


# ──────────────────────────────────────────────
# 11. BOOKINGS (GET)
# ──────────────────────────────────────────────
@router.get("/tenants/{tenant_id}/bookings")
async def get_bookings(
    tenant_id: int,
    db: Session = Depends(get_db)
):
    """Get all bookings for a tenant"""
    bookings = db.query(Booking).filter(
        Booking.tenant_id == tenant_id
    ).order_by(Booking.datetime.desc()).all()
    
    return [
        {
            "id": b.id,
            "datetime": b.datetime,
            "contact": b.contact,
            "status": b.status
        }
        for b in bookings
    ]


# ──────────────────────────────────────────────
# 12. LEADS (GET)
# ──────────────────────────────────────────────
@router.get("/tenants/{tenant_id}/leads")
async def get_leads(
    tenant_id: int,
    db: Session = Depends(get_db)
):
    """Get all leads for a tenant"""
    leads = db.query(Lead).filter(
        Lead.tenant_id == tenant_id
    ).order_by(Lead.created_at.desc()).all()
    
    return [
        {
            "id": l.id,
            "name": l.name,
            "phone": l.phone,
            "intent": l.intent,
            "status": l.status
        }
        for l in leads
    ]


# ──────────────────────────────────────────────
# 13. CONVERSATION MESSAGES (GET)
# ──────────────────────────────────────────────
@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: int,
    db: Session = Depends(get_db)
):
    """Get all messages for a conversation"""
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at).all()
    
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at
        }
        for m in messages
    ]


# ──────────────────────────────────────────────
# 14. DELETE TENANT (DELETE)
# ──────────────────────────────────────────────
@router.delete("/tenants/{tenant_id}")
async def delete_tenant(
    tenant_id: int,
    db: Session = Depends(get_db)
):
    """Delete a tenant and all related data"""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Delete in order to avoid foreign key violations
    db.query(Message).filter(Message.conversation_id.in_(
        db.query(Conversation.id).filter(Conversation.tenant_id == tenant_id)
    )).delete(synchronize_session=False)
    
    db.query(Conversation).filter(Conversation.tenant_id == tenant_id).delete()
    db.query(Booking).filter(Booking.tenant_id == tenant_id).delete()
    db.query(Lead).filter(Lead.tenant_id == tenant_id).delete()
    db.query(Configs).filter(Configs.tenant_id == tenant_id).delete()
    db.query(Document).filter(Document.tenant_id == tenant_id).delete()
    db.query(KnowledgeSource).filter(KnowledgeSource.tenant_id == tenant_id).delete()
    
    db.delete(tenant)
    db.commit()
    
    # Try to delete from Qdrant as well
    try:
        from qdrant_client.http import models
        client = get_qdrant_client()
        client.delete(
            collection_name="knowledge",
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="tenant_id",
                            match=models.MatchValue(value=tenant_id)
                        )
                    ]
                )
            )
        )
    except Exception as e:
        print(f"Qdrant delete error (ignored): {e}")
    
    return {"message": f"Tenant {tenant_id} deleted successfully"}


# ──────────────────────────────────────────────
# 15. USE TEMPLATE (POST)
# ──────────────────────────────────────────────
@router.post("/templates/{template_type}")
async def use_template(
    template_type: str,
    data: dict,
    db: Session = Depends(get_db)
):
    """Create a tenant using a vertical template"""
    
    import json
    import os
    
    template_files = {
        "clinic": "templates/clinic_template.json",
        "real_estate": "templates/realestate_template.json",
        "restaurant": "templates/restaurant_template.json"
    }
    
    template_file = template_files.get(template_type)
    if not template_file:
        raise HTTPException(status_code=404, detail="Template not found")
    
    if not os.path.exists(template_file):
        raise HTTPException(status_code=404, detail="Template file not found")
    
    with open(template_file, 'r') as f:
        template = json.load(f)
    
    tenant = create_tenant(
        db=db,
        name=data['name'],
        vertical=template['vertical'],
        phone_number=data['phone_number']
    )
    
    config = Configs(
        tenant_id=tenant.id,
        hours=template['config'].get('hours', {}),
        services=template['config'].get('services', []),
        booking_rules=template['config'].get('booking_rules', {}),
        persona=template.get('system_prompt', '')
    )
    db.add(config)
    db.commit()
    
    try:
        from ingestion import chunk_text, store_chunks_in_qdrant
        from qdrant_utils import get_qdrant_client
        
        client = get_qdrant_client()
        all_chunks = []
        
        source = KnowledgeSource(
            tenant_id=tenant.id,
            type="faq",
            name=f"{template_type}_template_faqs",
            status="completed"
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        
        for faq in template.get('faqs', []):
            chunks = chunk_text(faq, chunk_size=200, overlap=20)
            all_chunks.extend(chunks)
            
            for chunk in chunks:
                doc = Document(
                    source_id=source.id,
                    tenant_id=tenant.id,
                    chunk_text=chunk,
                    meta={"template": template_type}
                )
                db.add(doc)
        
        if all_chunks:
            store_chunks_in_qdrant(
                client=client,
                collection_name="knowledge",
                tenant_id=tenant.id,
                chunks=all_chunks,
                source_name=f"{template_type}_template.txt"
            )
            chunks_count = len(all_chunks)
        else:
            chunks_count = 0
            
        db.commit()
            
    except Exception as e:
        print(f"Error uploading FAQs: {e}")
        chunks_count = 0
    
    return {
        "message": f"Tenant '{tenant.name}' created from {template_type} template",
        "tenant_id": tenant.id,
        "vertical": template['vertical'],
        "config_applied": True,
        "faqs_uploaded": chunks_count,
        "status": tenant.status
    }
# api/admin.py — Add this after your existing endpoints

@router.put("/bookings/{booking_id}/status")
async def update_booking_status(
    booking_id: int,
    status: str,
    db: Session = Depends(get_db)
):
    """Update booking status (confirm, cancel, complete)"""
    
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    valid_statuses = ["pending", "confirmed", "cancelled", "completed", "no-show"]
    if status not in valid_statuses:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )
    
    booking.status = status
    db.commit()
    db.refresh(booking)
    
    return {
        "message": f"Booking {booking_id} status updated to {status}",
        "booking": {
            "id": booking.id,
            "contact_name": booking.contact_name,
            "service": booking.service,
            "date": booking.date,
            "time": booking.time,
            "status": booking.status
        }
    }