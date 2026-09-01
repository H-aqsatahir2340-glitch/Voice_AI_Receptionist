# Voice_AI_Receptionist

Multi-tenant voice + chat AI receptionist for clinics, restaurants, and real estate.

## Features
- Multi-tenant architecture (isolated data per business)
- Voice + Chat channels
- Appointment booking
- Lead capture
- Knowledge base (RAG)
- Admin Console

## Tech Stack
- FastAPI (Python)
- PostgreSQL + Qdrant
- Pipecat + Twilio
- Deepgram + ElevenLabs
- Groq LLM

## Setup
1. Clone the repo
2. Create virtual environment
3. Install dependencies
4. Add API keys in `.env`
5. Run Docker: `docker-compose up -d`
6. Start server: `uvicorn main:app --reload`

## API Keys Required
- Deepgram (STT)
- Groq (LLM)
- ElevenLabs (TTS)
- Twilio (Telephony)

## License
MIT
