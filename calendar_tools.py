
# llm_handler.py
import json
from datetime import datetime, timedelta
import re
from openai import OpenAI
from config import Config
import calendar_tools

def parse_date_from_text(text: str) -> str:
    """
    Convert natural language dates to YYYY-MM-DD.
    Examples: "tomorrow", "next Tuesday", "this upcoming Tuesday"
    """
    today = datetime.now().date()
    text_lower = text.lower()
    
    # Handle "tomorrow"
    if "tomorrow" in text_lower:
        return (today + timedelta(days=1)).isoformat()
    
    # Handle "next [day]" or "upcoming [day]"
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for day in days:
        if f"next {day}" in text_lower or f"upcoming {day}" in text_lower:
            target = days.index(day)
            current = today.weekday()
            days_ahead = target - current
            if days_ahead <= 0:
                days_ahead += 7
            return (today + timedelta(days=days_ahead)).isoformat()
    
    # Handle "this [day]"
    for day in days:
        if f"this {day}" in text_lower:
            target = days.index(day)
            current = today.weekday()
            days_ahead = target - current
            if days_ahead <= 0:
                days_ahead += 7
            return (today + timedelta(days=days_ahead)).isoformat()
    
    return None
# ──────────────────────────────────────────────
# CALENDAR DATA FUNCTIONS
# ──────────────────────────────────────────────

def load_calendar():
    """Load calendar from JSON file"""
    try:
        with open('calendar.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_calendar(calendar):
    """Save calendar to JSON file"""
    with open('calendar.json', 'w') as f:
        json.dump(calendar, f, indent=2)

def load_messages():
    """Load messages from JSON file"""
    try:
        with open('messages.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_messages(messages):
    """Save messages to JSON file"""
    with open('messages.json', 'w') as f:
        json.dump(messages, f, indent=2)

# ──────────────────────────────────────────────
# TOOL 1: CHECK AVAILABILITY
# ──────────────────────────────────────────────

def check_availability(date):
    """
    Check available slots for a date
    
    Args:
        date (str): Date in YYYY-MM-DD format
    
    Returns:
        str: Available slots or "No slots available"
    """
    calendar = load_calendar()
    slots = calendar.get(date, [])
    
    if slots:
        return f"Available slots on {date}: {', '.join(slots)}"
    else:
        return f"No slots available on {date}"

# ──────────────────────────────────────────────
# TOOL 2: BOOK APPOINTMENT
# ──────────────────────────────────────────────

def book_slot(date, time, caller_name="Caller"):
    """Book a reservation slot"""
    import re
    from llm_handler import parse_date_from_text
    
    # ──────────────────────────────────────────────
    # If date is natural language, parse it
    # ──────────────────────────────────────────────
    if not re.match(r'\d{4}-\d{2}-\d{2}', date):
        parsed_date = parse_date_from_text(date)
        if parsed_date:
            date = parsed_date
        else:
            return f"Sorry, I couldn't understand the date: {date}"
    
    calendar = load_calendar()
    
    # ──────────────────────────────────────────────
    # Check if date exists
    # ──────────────────────────────────────────────
    if date not in calendar:
        return f"No reservations available on {date}"
    
    # ──────────────────────────────────────────────
    # Handle time range (e.g., "11am-2pm")
    # ──────────────────────────────────────────────
    if " - " in time or " to " in time:
        # Book the start time (first part before "to" or "-")
        start_time = time.split(" to ")[0] if " to " in time else time.split(" - ")[0]
        start_time = start_time.strip()
        
        # Find the slot
        if start_time not in calendar[date]:
            return f"Sorry, {start_time} on {date} is not available"
        
        calendar[date].remove(start_time)
        save_calendar(calendar)
        return f"Successfully booked {caller_name} on {date} from {time}!"
    
    # ──────────────────────────────────────────────
    # Normal single time booking
    # ──────────────────────────────────────────────
    if time not in calendar[date]:
        return f"Sorry, {time} on {date} is not available"
    
    calendar[date].remove(time)
    save_calendar(calendar)
    
    return f"Successfully booked {time} on {date} for {caller_name}"
# ──────────────────────────────────────────────
# TOOL 3: LEAVE MESSAGE
# ──────────────────────────────────────────────

def leave_message(caller_name, message, callback_number=None):
    """
    Save a message from caller
    
    Args:
        caller_name (str): Caller's name
        message (str): Message content
        callback_number (str, optional): Caller's phone number
    
    Returns:
        str: Confirmation message
    """
    messages = load_messages()
    
    new_message = {
        "id": len(messages) + 1,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "caller_name": caller_name,
        "message": message,
        "callback_number": callback_number if callback_number else "Not provided",
        "status": "unread"
    }
    
    messages.append(new_message)
    save_messages(messages)
    
    return f"Message saved for {caller_name}"

# ──────────────────────────────────────────────
# TOOL 4: GET FAQ
# ──────────────────────────────────────────────

def get_faq(topic):
    """
    Answer frequently asked questions
    
    Args:
        topic (str): One of: hours, location, services, pricing
    
    Returns:
        str: Answer to the question
    """
    faqs = {
        "hours": "We're open Monday to Friday from 9 AM to 6 PM, Saturday from 10 AM to 4 PM, and closed on Sunday.",
        "location": "We're located at 123 Main Street, Suite 100, New York, NY 10001.",
        "services": "We offer consulting, training, support services, and custom solutions.",
        "pricing": "Our pricing varies by service. Please call back during business hours or leave a message and we'll email you a quote."
    }
    
    topic_lower = topic.lower()
    
    if topic_lower in faqs:
        return faqs[topic_lower]
    else:
        return "I don't have information on that topic. Please leave a message and we'll get back to you."