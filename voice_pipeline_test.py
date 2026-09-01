# voice_pipeline_test.py
from tts_handler import synthesize_speech
from stt_handler import transcribe_audio
from llm_handler import get_response

def main():
    print("=== Phase 3.4: Full Voice Pipeline Test ===\n")

    # Step 1: Simulate a caller speaking
    caller_text = "what are the available slots for friday 2 pm?"
    print(f"1. Simulated caller says: \"{caller_text}\"")
    caller_audio_path = synthesize_speech(caller_text, "pipeline_caller_input.mp3")
    print(f"   -> generated {caller_audio_path}")

    # Step 2: Transcribe that audio back to text
    print("\n2. Transcribing caller audio with Deepgram...")
    transcript = transcribe_audio(caller_audio_path)
    print(f"   -> transcript: \"{transcript}\"")

    # Step 3: Send the transcript to the LLM
    print("\n3. Sending transcript to the LLM (Groq)...")
    reply_text, _ = get_response(transcript, [])
    print(f"   -> LLM reply: \"{reply_text}\"")

    # Step 4: Convert the reply back to speech
    print("\n4. Converting reply to speech with ElevenLabs...")
    reply_audio_path = synthesize_speech(reply_text, "pipeline_reply_output.mp3")
    print(f"   -> generated {reply_audio_path}")

    print("\n✅ Full pipeline ran successfully. Play pipeline_reply_output.mp3 to hear the result.")

if __name__ == "__main__":
    main()