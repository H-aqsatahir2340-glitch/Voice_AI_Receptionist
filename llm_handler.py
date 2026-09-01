# llm_handler.py
import json
from openai import OpenAI
from config import Config
import calendar_tools
from datetime import datetime, timedelta
import re

# ──────────────────────────────────────────────
# 1. Initialize Groq Client (via OpenAI-compatible API)
# ──────────────────────────────────────────────

client = OpenAI(
    api_key=Config.GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# Use a Groq-supported model
MODEL = "openai/gpt-oss-120b"

# ──────────────────────────────────────────────
# 2. Date Parser Helper (converts natural language to YYYY-MM-DD)
# ──────────────────────────────────────────────

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
# 3. System Prompt (the "personality" of the agent)
# ──────────────────────────────────────────────
# llm_handler.py

SYSTEM_PROMPT = """You are a friendly, professional AI receptionist.

## YOUR ROLE
- You are the first point of contact for callers.
- You handle bookings, cancellations, and answer questions.
- You speak naturally and conversationally.

## BOOKING FLOW

### If user gives details one by one:
1. Ask for: Name
2. Ask for: Service
3. Ask for: Date
4. Ask for: Time
5. Ask for: Phone number

After each response, confirm and ask for the next piece.

### If user gives ALL details at once:
- Extract: name, service, date, time, phone
- Confirm: "Thanks [name]! Your [service] is booked for [date] at [time]."
- Ask if anything else is needed.

## CANCELLATION FLOW
If a user says "cancel", ask for their name, find the booking, and cancel it.

## RESPONSE STYLE
- Be warm and professional
- Keep responses to 1-2 sentences
- Confirm what you heard
- When all details are collected, confirm the booking

## EXAMPLES

### Step by step:
User: "I want to book"
You: "I'd be happy to help! What's your full name?"

User: "Aqsa Tahir"
You: "Thanks Aqsa! What service would you like?"

User: "Scaling"
You: "Great! What date would you prefer?"

User: "26 August"
You: "What time works best for you?"

User: "2pm"
You: "And what's your phone number?"

User: "03156789005"
You: "✅ Thanks Aqsa! Your scaling is booked for 26 August at 2pm."

### All at once:
User: "My name is Aqsa Tahir, I need scaling on 26 August at 2pm, my phone is 03156789005"
You: "✅ Thanks Aqsa! Your scaling is booked for 26 August at 2pm. You'll receive a confirmation."

## RULES
- NEVER list all questions at once.
- Ask ONE question at a time (if details are missing).
- Always confirm what the user said.
- If all details are provided, confirm immediately.
- If you don't know something, say so.
"""
# ──────────────────────────────────────────────
# 4. Tool Definitions (what the LLM can call)
# ──────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check open appointment slots for a given date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format"}
                },
                "required": ["date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_slot",
            "description": "Book an appointment slot for a caller.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                    "time": {"type": "string", "description": "Time like '9:00 AM' or '14:00' (24-hour)"},
                    "caller_name": {"type": "string", "description": "Name of the caller booking the slot"}
                },
                "required": ["date", "time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "leave_message",
            "description": "Save a message from the caller when their request can't be handled directly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "caller_name": {"type": "string", "description": "Caller's full name"},
                    "message": {"type": "string", "description": "The message content"},
                    "callback_number": {"type": "string", "description": "Caller's phone number (optional)"}
                },
                "required": ["caller_name", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_faq",
            "description": "Look up an answer to a common question: hours, location, services, or pricing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "One of: hours, location, services, pricing"
                    }
                },
                "required": ["topic"]
            }
        }
    }
]

# ──────────────────────────────────────────────
# 5. Map Tool Names to Python Functions
# ──────────────────────────────────────────────

AVAILABLE_TOOLS = {
    "check_availability": calendar_tools.check_availability,
    "book_slot": calendar_tools.book_slot,
    "leave_message": calendar_tools.leave_message,
    "get_faq": calendar_tools.get_faq,
}

# ──────────────────────────────────────────────
# 6. Main Function: Process Caller Message
# ──────────────────────────────────────────────

def get_response(user_message: str, conversation_history: list) -> tuple:
    """
    Sends the caller's message (plus prior conversation) to the LLM,
    executes any tool calls it makes, and returns the final natural
    language reply.

    Args:
        user_message: what the caller just said
        conversation_history: list of {"role": ..., "content": ...} dicts

    Returns:
        (reply_text, updated_conversation_history)
    """

    # ──────────────────────────────────────────────
    # QUICK FAQ FALLBACK (before calling LLM)
    # ──────────────────────────────────────────────
    faq_keywords = {
        "hours": "We're open Monday to Friday from 9 AM to 6 PM, Saturday from 10 AM to 4 PM, and closed on Sunday.",
        "location": "We're located at 123 Main Street, Suite 100, New York, NY 10001.",
        "services": "We offer consulting, training, support services, and custom solutions.",
        "pricing": "Our pricing varies by service. Please call back during business hours or leave a message and we'll email you a quote."
    }
    
    user_lower = user_message.lower()
    for key, answer in faq_keywords.items():
        if key in user_lower:
            updated_history = conversation_history + [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": answer}
            ]
            return answer, updated_history

    # ──────────────────────────────────────────────
    # Build messages array
    # ──────────────────────────────────────────────
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history
    messages.append({"role": "user", "content": user_message})

    # Call Groq
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
    )

    reply = response.choices[0].message

    # ──────────────────────────────────────────────
    # If the model wants to call a tool, run it
    # ──────────────────────────────────────────────
    if reply.tool_calls:
        print(f"🔧 TOOL CALLED: {reply.tool_calls}")  # Debug log
        
        messages.append(reply)

        for tool_call in reply.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)

            print(f"🔧 Executing: {func_name} with {func_args}")  # Debug log

            if func_name in AVAILABLE_TOOLS:
                result = AVAILABLE_TOOLS[func_name](**func_args)
            else:
                result = {"error": f"Unknown tool: {func_name}"}

            print(f"📊 Tool result: {result}")  # Debug log

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })

        # Ask the model to turn the tool result into a natural reply
        followup = client.chat.completions.create(
            model=MODEL,
            messages=messages,
        )
        final_reply = followup.choices[0].message.content
        messages.append({"role": "assistant", "content": final_reply})
    else:
        final_reply = reply.content
        messages.append({"role": "assistant", "content": final_reply})

    # Return updated conversation (without system prompt)
    updated_history = messages[1:]  # drop system message

    return final_reply, updated_history

# ──────────────────────────────────────────────
# 7. RAG Response (for non-chat contexts)
# ──────────────────────────────────────────────

def get_rag_response(prompt: str) -> str:
    try:
        print(f"🤖 Calling LLM...")
        messages = [{"role": "user", "content": prompt}]
        
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=500
        )
        
        result = response.choices[0].message.content
        print(f"✅ LLM returned: {result[:50]}...")
        return result
        
    except Exception as e:
        print(f"❌ LLM Error: {e}")
        raise