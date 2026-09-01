# voice_main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from pipecat.pipeline.runner import WorkerRunner
from pipecat.transports.websocket.fastapi import FastAPIWebsocketTransport
from rag.pipeline import rag_answer
from twilio.twiml.voice_response import VoiceResponse
import json

# ──────────────────────────────────────────────
# 1. CREATE FastAPI APP FIRST
# ──────────────────────────────────────────────
app = FastAPI(title="Voice AI Receptionist")

# ──────────────────────────────────────────────
# 2. TWILIO WEBHOOK ENDPOINT
# ──────────────────────────────────────────────
@app.post("/twilio/incoming")
async def twilio_incoming(request: Request):
    """Twilio webhook for incoming calls"""
    
    response = VoiceResponse()
    
    # Get the Twilio phone number dialed
    form_data = await request.form()
    to_number = form_data.get("To")
    
    # Resolve tenant from phone number
    from tenant_resolver import resolve_tenant_from_phone
    from database import SessionLocal
    
    db = SessionLocal()
    tenant = resolve_tenant_from_phone(to_number)
    db.close()
    
    if not tenant:
        response.say("Sorry, this number is not recognized.")
        return Response(str(response), media_type="text/xml")
    
    # Connect to WebSocket
    response.connect().stream(
        url=f"wss://{request.headers.get('host')}/ws/{tenant.id}"
    )
    
    return Response(str(response), media_type="text/xml")

# ──────────────────────────────────────────────
# 3. WEBSOCKET ENDPOINT
# ──────────────────────────────────────────────
@app.websocket("/ws/{tenant_id}")
async def websocket_endpoint(websocket: WebSocket, tenant_id: int):
    """WebSocket endpoint for Twilio voice calls"""
    
    await websocket.accept()
    print(f"🔊 WebSocket connected for tenant {tenant_id}")
    
    try:
        # Test connection
        await websocket.send_text(json.dumps({"type": "connected", "message": "Hello from Voice AI!"}))
        
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            print(f"Received: {data}")
            
            # Process with RAG
            answer, chunks = rag_answer(tenant_id, data)
            
            await websocket.send_text(json.dumps({"type": "response", "text": answer}))
            
    except WebSocketDisconnect:
        print(f"🔇 WebSocket disconnected for tenant {tenant_id}")
    except Exception as e:
        print(f"❌ Error: {e}")

# ──────────────────────────────────────────────
# 4. HEALTH CHECK
# ──────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "Voice AI Receptionist"}

# ──────────────────────────────────────────────
# 5. RUN SERVER
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)