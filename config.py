# config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Deepgram (Speech-to-Text)
    DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY')
    
    # Groq (LLM - Brain)
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    
    # ElevenLabs (Text-to-Speech)
    ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
    
    # Twilio (Phone Service)
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')

    # LLM Provider
    LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'groq')
    # Optional: Default voice for ElevenLabs (you'll update this later)
    ELEVENLABS_VOICE_ID = os.getenv('ELEVENLABS_VOICE_ID', '21m00Tcm4TlvDq8ikWAM')