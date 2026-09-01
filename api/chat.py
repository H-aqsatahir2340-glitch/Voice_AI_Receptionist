# api/chat.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from database import SessionLocal
from models import Tenant, Message, Conversation, Booking, Lead
from rag.pipeline import rag_answer
from datetime import datetime
from api.auth import verify_api_key
import re

router = APIRouter()

class ChatRequest(BaseModel):
    tenant_id: int
    message: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    conversation_id: str


# ──────────────────────────────────────────────
# BOOKING SESSION STORE
# ──────────────────────────────────────────────
booking_sessions = {}

def get_booking_session(conversation_id: int):
    if conversation_id not in booking_sessions:
        booking_sessions[conversation_id] = {
            'name': None,
            'phone': None,
            'service': None,
            'date': None,
            'time': None,
            'step': 0
        }
    return booking_sessions[conversation_id]

def clear_booking_session(conversation_id: int):
    if conversation_id in booking_sessions:
        del booking_sessions[conversation_id]


# ──────────────────────────────────────────────
# EXTRACTION FUNCTIONS
# ──────────────────────────────────────────────
def extract_name(text: str) -> Optional[str]:
    patterns = [
        r'my name is ([a-zA-Z\s]+?)(?:,|;|$|\.|and)',
        r'name is ([a-zA-Z\s]+?)(?:,|;|$|\.|and)',
        r'i am ([a-zA-Z\s]+?)(?:,|;|$|\.|and)',
        r'([a-zA-Z]+\s+[a-zA-Z]+)(?:\s|$|,)'
    ]
    for p in patterns:
        match = re.search(p, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip().title()
            if len(name) > 2:
                return name
    return None

def extract_phone(text: str) -> Optional[str]:
    cleaned = text.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    match = re.search(r'(\+?\d{10,15})', cleaned)
    if match:
        return match.group(1)
    return None

def extract_service(text: str) -> Optional[str]:
    services = ['root canal', 'cleaning', 'checkup', 'consultation', 'whitening', 
                'implant', 'crown', 'bridge', 'filling', 'extraction', 'scaling',
                'general dentistry', 'cosmetic dentistry', 'emergency']
    for s in services:
        if s in text.lower():
            return s.title()
    return None

def extract_date(text: str) -> Optional[str]:
    patterns = [
        r'(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*\d{4})',
        r'(\d{1,2}/\d{1,2}/\d{4})',
        r'(\d{4}-\d{2}-\d{2})'
    ]
    for p in patterns:
        match = re.search(p, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None

def extract_time(text: str) -> Optional[str]:
    patterns = [
        r'(\d{1,2}\s*(?:am|pm))',
        r'at\s*(\d{1,2})'
    ]
    for p in patterns:
        match = re.search(p, text, re.IGNORECASE)
        if match:
            time_str = match.group(1)
            if not any(x in time_str for x in ['am', 'pm']):
                time_str += ' PM'
            return time_str
    return None


# ──────────────────────────────────────────────
# MAIN CHAT ENDPOINT
# ──────────────────────────────────────────────
@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    tenant: Tenant = Depends(verify_api_key)
):
    db = SessionLocal()
    
    try:
        # ─── 1. CREATE CONVERSATION ───
        conversation = Conversation(
            tenant_id=tenant.id,
            channel="chat",
            started_at=datetime.now()
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        conv_id = conversation.id
        
        # ─── 2. GET HISTORY ───
        history = []
        if request.conversation_id:
            prev_messages = db.query(Message).filter(
                Message.conversation_id == int(request.conversation_id)
            ).order_by(Message.created_at).all()
            for msg in prev_messages:
                history.append({"role": msg.role, "content": msg.content})
        
        # ─── 3. GET RAG ANSWER ───
        answer, chunks = rag_answer(tenant.id, request.message, history)
        
        # ─── 4. SAVE MESSAGES ───
        user_msg = Message(
            tenant_id=tenant.id,
            conversation_id=conv_id,
            role="user",
            content=request.message
        )
        db.add(user_msg)
        
        assistant_msg = Message(
            tenant_id=tenant.id,
            conversation_id=conv_id,
            role="assistant",
            content=answer
        )
        db.add(assistant_msg)
        
        # ──────────────────────────────────────────────
        # 5. SAVE BOOKING
        # ──────────────────────────────────────────────
        msg_lower = request.message.lower()
        
        # ─── Check for Cancellation ───
        if "cancel" in msg_lower and "appointment" in msg_lower:
            name = extract_name(request.message)
            if name:
                booking = db.query(Booking).filter(
                    Booking.tenant_id == tenant.id,
                    Booking.contact_name == name,
                    Booking.status.in_(["pending", "confirmed"])
                ).first()
                
                if booking:
                    booking.status = "cancelled"
                    db.commit()
                    answer = f"I've cancelled your appointment on {booking.date} at {booking.time}."
                    print(f"📅 ❌ Booking cancelled for {name}")
                else:
                    answer = "I couldn't find a booking to cancel. Please check your name and try again."
            else:
                answer = "Please tell me your name so I can find your booking."
        
        # ─── Check for Booking ───
        elif any(word in msg_lower for word in ['book', 'appointment', 'scaling', 'cleaning', 'dentistry', 'schedule', 'reserve']):
            print("📋 Booking request detected!")
            
            # Get or create booking session
            session = get_booking_session(conv_id)
            
            # Extract details from message
            name = extract_name(request.message)
            phone = extract_phone(request.message)
            service = extract_service(request.message)
            date = extract_date(request.message)
            time = extract_time(request.message)
            
            # Update session with extracted details
            if name:
                session['name'] = name
            if phone:
                session['phone'] = phone
            if service:
                session['service'] = service
            if date:
                session['date'] = date
            if time:
                session['time'] = time
            
            print(f"📋 Session: {session}")
            
            # Check if we have ALL required fields
            if session['name'] and session['phone'] and session['service'] and session['date'] and session['time']:
                # ALL fields collected — SAVE!
                booking = Booking(
                    tenant_id=tenant.id,
                    conversation_id=conv_id,
                    contact_name=session['name'],
                    contact_phone=session['phone'],
                    service=session['service'],
                    date=session['date'],
                    time=session['time'],
                    status="pending"
                )
                db.add(booking)
                db.commit()
                db.refresh(booking)
                print(f"📅 ✅ Booking SAVED! ID: {booking.id} for {session['name']}")
                answer = f"✅ Booking confirmed! {session['name']} - {session['service']} on {session['date']} at {session['time']}."
                
                # Clear session after booking
                clear_booking_session(conv_id)
            
            else:
                # Build response with missing fields
                missing = []
                if not session['name']:
                    missing.append("name")
                if not session['phone']:
                    missing.append("phone number")
                if not session['service']:
                    missing.append("service")
                if not session['date']:
                    missing.append("date")
                if not session['time']:
                    missing.append("time")
                
                # Show what's already collected
                collected = []
                if session['name']:
                    collected.append(f"Name: {session['name']}")
                if session['phone']:
                    collected.append(f"Phone: {session['phone']}")
                if session['service']:
                    collected.append(f"Service: {session['service']}")
                if session['date']:
                    collected.append(f"Date: {session['date']}")
                if session['time']:
                    collected.append(f"Time: {session['time']}")
                
                response_parts = []
                if collected:
                    response_parts.append(f"I have: {', '.join(collected)}.")
                response_parts.append(f"I still need: {', '.join(missing)}.")
                response_parts.append("Please provide the missing details.")
                
                answer = " ".join(response_parts)
        
        db.commit()
        
        return ChatResponse(
            response=answer,
            conversation_id=str(conv_id)
        )
        
    except Exception as e:
        db.rollback()
        print(f"❌ Chat error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/health")
async def health():
    return {"status": "ok"}