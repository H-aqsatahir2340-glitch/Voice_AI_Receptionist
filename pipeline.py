# pipeline.py
import os
from dotenv import load_dotenv
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.transports.websocket.fastapi import FastAPIWebsocketTransport, FastAPIWebsocketParams  # ← ADDED
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame
from config import Config
from rag.pipeline import rag_answer
from llm_handler import get_rag_response

load_dotenv()

# ──────────────────────────────────────────────
# System Prompt
# ──────────────────────────────────────────────
SYSTEM_PROMPT = """You are a friendly, efficient AI receptionist.

Keep responses short and natural — this is spoken over the phone.
Always be helpful and professional.
"""

# ──────────────────────────────────────────────
# Create Pipeline
# ──────────────────────────────────────────────
async def create_pipeline(websocket, tenant_id: int):
    """Create a Pipecat pipeline for voice calls"""
    
    # ─── Transport ───
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
        )
    )
    
    # ─── STT (Deepgram) ───
    stt = DeepgramSTTService(
        api_key=Config.DEEPGRAM_API_KEY,
        model="nova-2",
        language="en"
    )
    
    # ─── LLM (Groq via OpenAI) ───
    llm = OpenAILLMService(
        api_key=Config.GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
        system_prompt=SYSTEM_PROMPT
    )
    
    # ─── TTS (ElevenLabs) ───
    tts = ElevenLabsTTSService(
        api_key=Config.ELEVENLABS_API_KEY,
        voice_id=Config.ELEVENLABS_VOICE_ID,
        model="eleven_turbo_v2_5"
    )
    
    # ─── Context ───
    context = LLMContext(messages=[{"role": "system", "content": SYSTEM_PROMPT}])
    context_aggregator = LLMContextAggregatorPair(context)
    
    # ─── Custom Function for RAG ───
    async def rag_function(query: str):
        """Retrieve and generate response using RAG"""
        answer, chunks = rag_answer(tenant_id, query)
        return answer
    
    # ─── Pipeline ───
    pipeline = Pipeline([
        transport.input(),
        stt,
        context_aggregator.user(),
        llm,
        tts,
        transport.output(),
        context_aggregator.assistant(),
    ])
    
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        )
    )
    
    # ─── Trigger greeting when connected ───
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        await task.queue_frames([LLMRunFrame()])
    
    return task, transport