# test_stt.py
from stt_handler import transcribe_audio

# Make sure you have a test audio file called "test_audio.wav"
result = transcribe_audio("test_audio.wav")
print(f"Transcription: {result}")