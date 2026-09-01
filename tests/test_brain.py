# test_brain.py
from llm_handler import get_response

print("🧠 Testing the Brain (Text-Only)")
print("=" * 50)
print("Type your messages to test the AI receptionist.")
print("Type 'exit' to quit.")
print("=" * 50)

conversation = []

while True:
    user_input = input("\n👤 You: ")
    
    if user_input.lower() in ['exit', 'quit', 'bye']:
        print("👋 Goodbye!")
        break
    
    response, conversation = get_response(user_input, conversation)
    
    print(f"🤖 AI: {response}")
