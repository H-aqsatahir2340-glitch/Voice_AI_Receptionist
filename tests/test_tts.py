# test_tts.py
from tts_handler import synthesize_speech

print("🔊 Testing TTS...")

# Test text
text = "Hello! This is a test of the AI receptionist voice."

# Generate speech
output_file = synthesize_speech(text, "test_output.mp3")

if output_file:
    print(f"✅ Audio generated: {output_file}")
    print("📢 Play the file to hear your voice!")
else:
    print("❌ TTS failed. Check your API key and voice ID.")