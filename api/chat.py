# api/chat.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from database import SessionLocal
from models import Tenant, Message, Conversation, Booking, Lead
from rag.pipeline import rag_answer
from datetime import datetime, timedelta, time
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
            'active': False,   # explicit flag — a booking is "in progress"
                               # the moment intent is detected, regardless
                               # of whether any fields were extractable yet
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
# BOOKING INTENT
# ──────────────────────────────────────────────
# FIX (Bug #2): only clear "I want to book/schedule something" phrases here.
# Bare service names (scaling, cleaning, dentistry...) used to be in this
# list, which meant an FAQ question like "how much does scaling cost?"
# was misrouted into the booking flow and silently threw away the RAG
# answer. Service names alone are no longer enough to trigger this branch.
BOOKING_INTENT_WORDS = ['book', 'appointment', 'schedule', 'reserve', 'reservation']

def is_booking_intent(msg_lower: str, session: dict) -> bool:
    """
    Booking branch fires if either:
      - the message clearly signals booking intent, OR
      - a booking is already in progress for this conversation
        (so follow-up turns like "26 August" or "03156789005"
        keep landing in the booking flow instead of falling
        through to a generic RAG answer).
    """
    if any(word in msg_lower for word in BOOKING_INTENT_WORDS):
        return True
    return session.get('active', False)


# ──────────────────────────────────────────────
# EXTRACTION FUNCTIONS
# ──────────────────────────────────────────────
def extract_name(text: str) -> Optional[str]:
    # FIX (Bug #3): the old fallback pattern `([a-zA-Z]+\s+[a-zA-Z]+)` matched
    # ANY two consecutive words, so "book appointment please" could be
    # captured as the name "Book Appointment". Removed — only explicit
    # self-identification phrases are trusted now. Better to ask again
    # than to silently store a wrong name.
    patterns = [
        r'my name is ([a-zA-Z\s]+?)(?:,|;|$|\.|and)',
        r'name is ([a-zA-Z\s]+?)(?:,|;|$|\.|and)',
        r"i'?m ([a-zA-Z\s]+?)(?:,|;|$|\.|and)",
        r'i am ([a-zA-Z\s]+?)(?:,|;|$|\.|and)',
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

MONTHS = ["jan", "feb", "mar", "apr", "may", "jun",
          "jul", "aug", "sep", "oct", "nov", "dec"]
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

def extract_date(text: str) -> Optional[str]:
    """
    FIX (Bug #4): the old version required a 4-digit year, so a natural
    "26 August" (no year) never matched and the booking could never
    complete. Now handles: explicit years, year-optional "26 August",
    "tomorrow", and "next/this <weekday>" — returned as YYYY-MM-DD so
    it's consistent for storage either way.
    """
    text_lower = text.lower()
    today = datetime.now().date()

    # ISO format: 2026-08-26
    match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
    if match:
        return match.group(1)

    # DD/MM/YYYY or MM/DD/YYYY as given (kept as-is, matches old behavior)
    match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', text)
    if match:
        return match.group(1)

    # "26 August 2026" or "26 August" (year optional)
    match = re.search(
        r'(\d{1,2})\s+(' + '|'.join(MONTHS) + r')[a-z]*\s*(\d{4})?',
        text_lower
    )
    if match:
        day = int(match.group(1))
        month = MONTHS.index(match.group(2)) + 1
        year = int(match.group(3)) if match.group(3) else today.year
        try:
            candidate = datetime(year, month, day).date()
        except ValueError:
            return None
        # If no year was given and the date already passed this year,
        # assume next year.
        if not match.group(3) and candidate < today:
            candidate = datetime(year + 1, month, day).date()
        return candidate.isoformat()

    # "tomorrow"
    if "tomorrow" in text_lower:
        return (today + timedelta(days=1)).isoformat()

    # "next <weekday>" / "upcoming <weekday>" / "this <weekday>"
    for day in WEEKDAYS:
        if f"next {day}" in text_lower or f"upcoming {day}" in text_lower or f"this {day}" in text_lower:
            target = WEEKDAYS.index(day)
            current = today.weekday()
            days_ahead = target - current
            if days_ahead <= 0:
                days_ahead += 7
            return (today + timedelta(days=days_ahead)).isoformat()

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
            if not any(x in time_str.lower() for x in ['am', 'pm']):
                time_str += ' PM'
            return time_str
    return None

def combine_date_time(date_str: str, time_str: str) -> datetime:
    """
    Combine a YYYY-MM-DD date string and a free-text time string
    ("2 pm", "2:30pm", "14:00") into a real datetime object.

    FIX (datetime NOT NULL bug): the `bookings.datetime` column is
    NOT NULL in the deployed DB (a leftover constraint from before
    `date`/`time` were split into their own string columns — see the
    `# ← ADD THIS` comments in models.py). chat.py was only ever
    writing `date`/`time` and leaving `datetime` as None, which
    crashed the insert. Falls back to midnight if the time text
    can't be parsed, so this never returns None.
    """
    year, month, day = (int(p) for p in date_str.split('-'))
    hour, minute = 0, 0
    match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', time_str, re.IGNORECASE)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        meridiem = (match.group(3) or '').lower()
        if meridiem == 'pm' and hour != 12:
            hour += 12
        elif meridiem == 'am' and hour == 12:
            hour = 0
    return datetime(year, month, day, hour, minute)


# ──────────────────────────────────────────────
# LABELED-FIELD PARSING (Name: X, Phone: Y, Service: Z ...)
# ──────────────────────────────────────────────
# Free-text extraction (extract_name/extract_service/etc.) breaks on
# typos and unusual phrasing. When the bot itself asks the user to
# reply in "Field: value" form, this parses that reliably — no
# guessing, no fixed keyword list to mismatch against.
LABEL_PATTERNS = {
    'name':    r'name\s*[:=]\s*([^,;\n]+)',
    'phone':   r'(?:phone|contact)(?:\s*(?:no\.?|number))?\s*[:=]\s*([^,;\n]+)',
    'service': r'service\s*[:=]\s*([^,;\n]+)',
    'date':    r'date\s*[:=]\s*([^,;\n]+)',
    'time':    r'time\s*[:=]\s*([^,;\n]+)',
}

def extract_labeled_fields(text: str) -> dict:
    """Parse explicit 'Field: value' labels out of a message."""
    found = {}
    for field, pattern in LABEL_PATTERNS.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            found[field] = match.group(1).strip()
    return found


def get_tenant_services(db, tenant_id: int) -> list:
    """Fetch the tenant's actual configured services (from the clinic
    template / admin config) so the numbered service picker reflects
    real options instead of a hardcoded generic list."""
    from models import Configs
    config = db.query(Configs).filter(Configs.tenant_id == tenant_id).first()
    if config and config.services:
        return list(config.services)
    return []


# ──────────────────────────────────────────────
# SLOT AVAILABILITY
# ──────────────────────────────────────────────
# No slots/calendar table exists in the schema, so availability is
# derived on the fly from Configs.hours (business hours) minus
# whatever's already in the bookings table for that tenant/day.
SLOT_DURATION_MINUTES = 30  # default appointment length. If different
                            # services need different lengths later,
                            # this should move into Configs.booking_rules
                            # or a per-service field — flagging for now.

def parse_hours_range(hours_str: Optional[str]):
    """Parse a business-hours string like '9am-6pm' into
    (start_time, end_time). Returns None if closed/unparseable."""
    if not hours_str or hours_str.strip().lower() == "closed":
        return None
    parts = hours_str.lower().replace(' ', '').split('-')
    if len(parts) != 2:
        return None

    def parse_one(t):
        m = re.match(r'(\d{1,2})(?::(\d{2}))?(am|pm)', t)
        if not m:
            return None
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        if m.group(3) == 'pm' and hour != 12:
            hour += 12
        elif m.group(3) == 'am' and hour == 12:
            hour = 0
        return time(hour, minute)

    start, end = parse_one(parts[0]), parse_one(parts[1])
    if start is None or end is None:
        return None
    return (start, end)


def generate_day_slots(hours_str: Optional[str], slot_minutes: int = SLOT_DURATION_MINUTES) -> list:
    """All bookable slot start times (as time objects) for one day's hours string."""
    parsed = parse_hours_range(hours_str)
    if not parsed:
        return []
    start, end = parsed
    anchor = datetime(2000, 1, 1)
    current = datetime.combine(anchor, start)
    end_dt = datetime.combine(anchor, end)
    slots = []
    while current < end_dt:
        slots.append(current.time())
        current += timedelta(minutes=slot_minutes)
    return slots


def get_tenant_config(db, tenant_id: int):
    from models import Configs
    return db.query(Configs).filter(Configs.tenant_id == tenant_id).first()


def get_taken_times(db, tenant_id: int, day) -> set:
    """Times already booked (pending/confirmed) for a tenant on a given date."""
    day_start = datetime.combine(day, time.min)
    day_end = datetime.combine(day, time.max)
    existing = db.query(Booking).filter(
        Booking.tenant_id == tenant_id,
        Booking.status.in_(["pending", "confirmed"]),
        Booking.datetime >= day_start,
        Booking.datetime <= day_end,
    ).all()
    return {b.datetime.time() for b in existing if b.datetime}


def find_alternative_slots(db, tenant_id: int, hours_map: dict, start_date,
                            max_results: int = 3, max_days_ahead: int = 7) -> list:
    """Search forward from start_date for open slots, skipping closed
    days and already-booked times. Returns up to max_results datetimes."""
    alternatives = []
    for day_offset in range(max_days_ahead + 1):
        day = start_date + timedelta(days=day_offset)
        weekday_name = day.strftime('%A').lower()
        day_slots = generate_day_slots(hours_map.get(weekday_name))
        if not day_slots:
            continue
        taken = get_taken_times(db, tenant_id, day)
        for slot_time in day_slots:
            candidate = datetime.combine(day, slot_time)
            if candidate <= datetime.now():
                continue
            if slot_time in taken:
                continue
            alternatives.append(candidate)
            if len(alternatives) >= max_results:
                return alternatives
    return alternatives


def check_slot_availability(db, tenant, requested_dt: datetime):
    """
    Returns (available: bool, reason: Optional[str], alternatives: list[datetime]).
    reason/alternatives are only populated when available is False.
    """
    config = get_tenant_config(db, tenant.id)
    hours_map = (config.hours if config and config.hours else {}) or {}
    booking_rules = (config.booking_rules if config else {}) or {}

    advance_notice_hours = 0
    if isinstance(booking_rules, dict):
        advance_notice_hours = booking_rules.get('advance_notice', 0) or 0

    if requested_dt < datetime.now() + timedelta(hours=advance_notice_hours):
        alternatives = find_alternative_slots(db, tenant.id, hours_map, requested_dt.date())
        return False, f"We need at least {advance_notice_hours} hours' notice for bookings.", alternatives

    weekday_name = requested_dt.strftime('%A').lower()
    hours_range = parse_hours_range(hours_map.get(weekday_name))
    if not hours_range:
        alternatives = find_alternative_slots(db, tenant.id, hours_map, requested_dt.date() + timedelta(days=1))
        return False, f"We're closed on {requested_dt.strftime('%A')}.", alternatives

    start, end = hours_range
    if not (start <= requested_dt.time() < end):
        alternatives = find_alternative_slots(db, tenant.id, hours_map, requested_dt.date())
        return False, f"That's outside our hours on {requested_dt.strftime('%A')} ({hours_map.get(weekday_name)}).", alternatives

    taken = get_taken_times(db, tenant.id, requested_dt.date())
    if requested_dt.time() in taken:
        alternatives = find_alternative_slots(db, tenant.id, hours_map, requested_dt.date())
        return False, "That time is already booked.", alternatives

    return True, None, []


# ──────────────────────────────────────────────
# MAIN CHAT ENDPOINT
# ──────────────────────────────────────────────
@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    tenant: Tenant = Depends(verify_api_key)
):
    db = SessionLocal()

    print(f"📎 Received conversation_id: {request.conversation_id}")

    try:
        # ──────────────────────────────────────────────
        # 1. GET OR CREATE CONVERSATION
        # ──────────────────────────────────────────────
        # FIX (Bug #1): the old code created a brand-new Conversation row
        # on EVERY message, even when request.conversation_id was already
        # supplied. That gave a fresh conv_id each turn, which reset
        # booking_sessions[conv_id] every time — so multi-turn booking
        # details (name, then phone, then date...) could never accumulate.
        conversation = None
        if request.conversation_id:
            conversation = db.query(Conversation).filter(
                Conversation.id == int(request.conversation_id),
                Conversation.tenant_id == tenant.id
            ).first()

        if not conversation:
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
        prev_messages = db.query(Message).filter(
            Message.conversation_id == conv_id
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

        # ──────────────────────────────────────────────
        # 5. BOOKING / CANCELLATION HANDLING
        # ──────────────────────────────────────────────
        msg_lower = request.message.lower()
        session = get_booking_session(conv_id)

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

        # ─── Check for Booking (clear intent, or an in-progress session) ───
        elif is_booking_intent(msg_lower, session):
            print("📋 Booking request detected!")
            session['active'] = True  # flip on now, so the next turn is
                                       # still routed here even if this
                                       # turn extracted nothing

            # 1. Try explicit labeled fields first (most reliable — no
            #    typo/keyword-list dependence): "Name: X, Phone: Y"
            labeled = extract_labeled_fields(request.message)
            for field, value in labeled.items():
                if field == 'date':
                    # FIX: a labeled date ("date: 22 november 2026") was
                    # being stored as raw text instead of normalized to
                    # YYYY-MM-DD, which later crashed combine_date_time's
                    # date_str.split('-'). Run it through extract_date()
                    # the same way a free-text date would be.
                    normalized = extract_date(value)
                    session['date'] = normalized if normalized else value
                else:
                    session[field] = value

            # 2. Fill in anything still missing via free-text extraction
            if not session['name']:
                name = extract_name(request.message)
                if name:
                    session['name'] = name
            if not session['phone']:
                phone = extract_phone(request.message)
                if phone:
                    session['phone'] = phone
            if not session['service']:
                service = extract_service(request.message)
                if service:
                    session['service'] = service
                else:
                    # 3. Numbered-service fallback: if we just showed a
                    # numbered list (below), accept a bare number reply
                    # matched against the tenant's real services.
                    services_list = get_tenant_services(db, tenant.id)
                    if services_list:
                        num_match = re.match(r'^\s*(\d+)\s*$', request.message.strip())
                        if num_match:
                            idx = int(num_match.group(1)) - 1
                            if 0 <= idx < len(services_list):
                                session['service'] = services_list[idx]
            if not session['date']:
                date = extract_date(request.message)
                if date:
                    session['date'] = date
            if not session['time']:
                time = extract_time(request.message)
                if time:
                    session['time'] = time

            print(f"📋 Session: {session}")

            # Check if we have ALL required fields
            if session['name'] and session['phone'] and session['service'] and session['date'] and session['time']:
                # ALL fields collected — check availability before saving
                try:
                    booking_datetime = combine_date_time(session['date'], session['time'])
                except (ValueError, TypeError) as e:
                    print(f"⚠️ Could not parse '{session['date']}' / '{session['time']}' for datetime column: {e}")
                    try:
                        booking_datetime = datetime.strptime(session['date'], "%Y-%m-%d")
                    except ValueError:
                        # Last resort: still can't parse the stored date
                        # string at all — don't crash the request, fall
                        # back to today so the booking still saves and
                        # can be corrected by staff afterward.
                        print(f"⚠️ '{session['date']}' is not a usable date at all — defaulting to today")
                        booking_datetime = datetime.now()

                available, unavailable_reason, alternatives = check_slot_availability(
                    db, tenant, booking_datetime
                )

                if not available:
                    # Slot doesn't work — clear just date/time so the user
                    # can pick a new one without re-entering name/phone/service.
                    session['date'] = None
                    session['time'] = None
                    if alternatives:
                        alt_text = "; ".join(
                            dt.strftime("%a %d %b, %I:%M %p") for dt in alternatives
                        )
                        answer = (
                            f"{unavailable_reason} Here are some open times instead: "
                            f"{alt_text}. Which works for you? "
                            f"(e.g. \"Date: 25 September\", \"Time: 2pm\")"
                        )
                    else:
                        answer = (
                            f"{unavailable_reason} I couldn't find an open slot in the "
                            f"next week — please call us directly, or try a different date."
                        )
                else:
                    booking = Booking(
                        tenant_id=tenant.id,
                        conversation_id=conv_id,
                        contact_name=session['name'],
                        contact_phone=session['phone'],
                        service=session['service'],
                        date=session['date'],
                        time=session['time'],
                        datetime=booking_datetime,
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
                # Ask for exactly ONE missing field at a time — easier for
                # the user to answer, and easier to parse reliably than a
                # jumbled multi-field sentence.
                if not session['name']:
                    answer = "What's the patient's full name? (e.g. \"Name: Aqsa Tahir\")"
                elif not session['phone']:
                    answer = "What's the best contact number? (e.g. \"Phone: 03001234567\")"
                elif not session['service']:
                    services_list = get_tenant_services(db, tenant.id)
                    if services_list:
                        options = "\n".join(f"{i+1}) {s}" for i, s in enumerate(services_list))
                        answer = f"Which service would you like?\n{options}\n(Reply with the number, or \"Service: <name>\")"
                    else:
                        answer = "Which service would you like? (e.g. \"Service: Scaling\")"
                elif not session['date']:
                    answer = "What date works for you? (e.g. \"Date: 25 September\" or 2026-09-25)"
                elif not session['time']:
                    answer = "What time? (e.g. \"Time: 2pm\")"

                # Show a short recap of what's already collected so far,
                # so the user isn't asking "wait, did that save?"
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
                if collected:
                    answer = f"Got it — {', '.join(collected)}. {answer}"

        # ─── Otherwise: plain RAG answer (untouched) ───
        # `answer` already holds the rag_answer() result from step 3 —
        # this is the branch that was previously unreachable for any
        # message that happened to mention a service name.

        assistant_msg = Message(
            tenant_id=tenant.id,
            conversation_id=conv_id,
            role="assistant",
            content=answer
        )
        db.add(assistant_msg)

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
