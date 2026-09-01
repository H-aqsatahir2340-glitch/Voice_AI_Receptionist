# test_chat.py
import requests
from database import SessionLocal
from models import Tenant

db = SessionLocal()
tenant = db.query(Tenant).filter(Tenant.id == 8).first()
db.close()

if not tenant:
    print('Tenant 8 not found')
    exit()

print('='*50)
print(f'Chatting with: {tenant.name}')
print('Type your questions. Type exit to quit.')
print('='*50)

conversation_id = None

while True:
    user_input = input('\nYou: ')
    
    if user_input.lower() in ['exit', 'quit', 'bye']:
        print('Goodbye!')
        break
    
    try:
        response = requests.post(
            'http://localhost:8000/chat',
            headers={
                'x-api-key': tenant.api_key,
                'Content-Type': 'application/json'
            },
            json={
                'tenant_id': 8,
                'message': user_input,
                'conversation_id': conversation_id
            }
        )
        
        data = response.json()
        
        if 'response' in data:
            print(f'AI: {data["response"]}')
            conversation_id = data.get('conversation_id')
        else:
            print(f'Error: {data}')
            
    except Exception as e:
        print(f'Error: {e}')