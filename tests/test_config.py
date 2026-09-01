from config import Config

print("✅ Config loaded successfully!")
print("=" * 40)

print(f"Deepgram API Key: {Config.DEEPGRAM_API_KEY[:10]}...")
print(f"Groq API Key: {Config.GROQ_API_KEY[:10]}...")
print(f"ElevenLabs API Key: {Config.ELEVENLABS_API_KEY[:10]}...")
print(f"Twilio SID: {Config.TWILIO_ACCOUNT_SID[:10]}...")
print(f"Twilio Auth Token: {Config.TWILIO_AUTH_TOKEN[:10]}...")
print(f"Twilio Phone Number: {Config.TWILIO_PHONE_NUMBER}")