# test_tools.py
from calendar_tools import *

print("🧪 Testing Tools")
print("=" * 40)

print("\n1. Testing check_availability:")
result = check_availability("2026-07-22")
print(f"   Date: {result['date']}")
print(f"   Available slots: {result['available']}")
print(f"   Has slots: {result['has_slots']}")

print("\n2. Testing book_slot:")
result = book_slot("2026-07-22", "9:00 AM", "John Doe")
print(f"   Success: {result['success']}")
print(f"   Message: {result['message']}")

print("\n3. Testing check_availability again (after booking):")
result = check_availability("2026-07-22")
print(f"   Available slots: {result['available']}")

print("\n4. Testing leave_message:")
result = leave_message("Jane Smith", "Need to discuss project", "+15551234567")
print(f"   Success: {result['success']}")
print(f"   Message: {result['message']}")
print(f"   ID: {result['message_id']}")

print("\n5. Testing get_faq:")
result = get_faq("hours")
print(f"   Topic: {result['topic']}")
print(f"   Answer: {result['answer']}")

result = get_faq("location")
print(f"   Topic: {result['topic']}")
print(f"   Answer: {result['answer']}")

print("\n✅ All tests completed!")