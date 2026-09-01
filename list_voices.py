# list_voices.py
from elevenlabs import ElevenLabs
from config import Config

client = ElevenLabs(api_key=Config.ELEVENLABS_API_KEY)

def main():
    print("=== Available ElevenLabs Voices ===\n")
    
    response = client.voices.get_all()
    
    for voice in response.voices:
        print(f"Name: {voice.name}")
        print(f"  Voice ID: {voice.voice_id}")
        print(f"  Category: {voice.category}")
        print()

if __name__ == "__main__":
    main()