# calendar_tools_db.py
from sqlalchemy.orm import Session
from models import Booking, Conversation
from datetime import datetime, timedelta

def check_availability_db(db: Session, tenant_id: int, date: str):
    """Check available slots for a tenant on a given date"""
    bookings = db.query(Booking).filter(
        Booking.tenant_id == tenant_id,
        Booking.datetime >= datetime.strptime(date, "%Y-%m-%d"),
        Booking.datetime < datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1),
        Booking.status == "confirmed"
    ).all()
    
    all_slots = ["9:00 AM", "10:00 AM", "11:00 AM", "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM"]
    booked_times = [b.datetime.strftime("%I:%M %p") for b in bookings]
    available = [s for s in all_slots if s not in booked_times]
    
    return available

def book_slot_db(db: Session, tenant_id: int, date: str, time: str, contact_name: str, contact_phone: str, conversation_id: int = None):
    """Book a slot for a tenant"""
    available = check_availability_db(db, tenant_id, date)
    
    if time not in available:
        return {"success": False, "message": f"Slot {time} on {date} is not available"}
    
    # Combine date and time
    dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %I:%M %p")
    
    booking = Booking(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        datetime=dt,
        contact={"name": contact_name, "phone": contact_phone},
        status="confirmed"
    )
    
    db.add(booking)
    db.commit()
    db.refresh(booking)
    
    return {
        "success": True,
        "message": f"Booked {time} on {date}",
        "booking_id": booking.id
    }