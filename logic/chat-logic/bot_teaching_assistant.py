"""
Spark — AI Teaching Companion
===============================
AI PC for Educators Course — Activity: Building Teaching Assistants

A voice-powered AI Teaching Companion that helps educators reduce
repetitive workload. Students speak questions, the bot answers using
your course materials — running 100% locally on your machine.

Run with: python bot_teaching_assistant.py
Open: http://localhost:7860/
"""

import asyncio
import os
import re
import sys
import json
import time
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.frames.frames import (
    Frame,
    TextFrame,
    TranscriptionFrame,
    LLMMessagesFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    TTSSpeakFrame,
    StartFrame,
    EndFrame,
)

from loguru import logger
from dotenv import load_dotenv

# Pipecat Imports
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.aggregators.sentence import SentenceAggregator

# Services
from pipecat.services.ollama.llm import OLLamaLLMService
from pipecat.services.kokoro.tts import KokoroTTSService
from pipecat.services.whisper.stt import WhisperSTTService

# Audio / VAD
from pipecat.audio.vad.silero import SileroVADAnalyzer, VADParams
from pipecat.processors.audio.vad_processor import VADProcessor

# Transport
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection

# Frameworks (RTVI is auto-added by PipelineTask)

# Local imports
from knowledge_base import (
    create_teaching_context,
    reload_materials,
    get_loaded_files,
    MODES,
)


# Load environment variables
load_dotenv()

logger.remove()
logger.add(sys.stderr, level="DEBUG")


# ============================================================
# TEXT CLEANUP (strip markdown/symbols before TTS)
# ============================================================

class TTSTextCleanup(FrameProcessor):
    """Strip markdown formatting and filenames before text reaches TTS."""

    @staticmethod
    def clean(text: str) -> str:
        # Paired markdown: **bold**, *italic*, __bold__, _italic_, `code`
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'_(.+?)_', r'\1', text)
        text = re.sub(r'`(.+?)`', r'\1', text)
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)  # [link](url)
        # Headings, bullet lists, numbered lists
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[-*+]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)
        # Strip any remaining asterisks, hashes, backticks
        text = re.sub(r'[*#`]', '', text)
        # Filenames: word.ext -> word
        _exts = ('txt', 'md', 'pdf', 'docx', 'py', 'json', 'csv', 'html', 'xml', 'yml', 'yaml')
        def _strip_ext(m):
            return m.group(0).rsplit('.', 1)[0] if m.group(0).split('.')[-1].lower() in _exts else m.group(0)
        text = re.sub(r'\w+\.\w{1,4}(?=[\s,;:.\)\]]|$)', _strip_ext, text)
        # Collapse whitespace
        text = re.sub(r'  +', ' ', text).strip()
        return text

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TextFrame):
            cleaned = self.clean(frame.text)
            if cleaned:
                await self.push_frame(TextFrame(text=cleaned), direction)
        else:
            await self.push_frame(frame, direction)


# ============================================================
# CONFIGURATION
# ============================================================

class Config:
    """Runtime configuration for Spark."""

    # Current teaching mode
    mode = os.getenv("DEFAULT_MODE", "faq")  # faq, assignment, lecture

    # Teaching style
    teaching_style = "supportive"  # supportive, socratic, concise

    # Custom educator instructions
    custom_instructions = ""

    # Course name
    course_name = os.getenv("COURSE_NAME", "Introduction to AI")

    # LLM parameters
    llm_params = {
        "temperature": float(os.getenv("LLM_TEMPERATURE", "0.3")),
        "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "150")),
    }


# Global context for real-time updates
global_context = None


# ============================================================
# TEACHING ASSISTANT IDENTITY
# ============================================================

TEACHING_STYLES = {
    "supportive": """
TEACHING STYLE — Supportive:
- Be warm, encouraging, and patient
- Acknowledge the student's effort before correcting
- Suggest next steps or additional resources
- Use phrases like "Great question!", "You're on the right track"
""",
    "socratic": """
TEACHING STYLE — Socratic:
- Guide students with questions rather than direct answers
- Help them discover the answer themselves
- Give hints, not solutions
- Use phrases like "What do you think would happen if...?", "Can you think of why...?"
""",
    "concise": """
TEACHING STYLE — Concise:
- Give brief, direct answers (1-2 sentences)
- No filler or pleasantries
- Get straight to the point
- Only elaborate if the student asks for more detail
""",
}

MODE_BEHAVIORS = {
    "faq": """
MODE — Course FAQ:
You answer logistical questions about the course: syllabus, schedule,
policies, grading, deadlines, office hours, etc.
Be factual. If the information comes from a specific document, mention it naturally (e.g. "according to the syllabus") but never say the filename.
""",
    "assignment": """
MODE — Assignment Help:
You help students with homework and assignments.
IMPORTANT: Never give direct answers. Instead:
- Give hints and guide their thinking
- Ask clarifying questions about their approach
- Point them to relevant sections of the assignment description
- Encourage them to attempt a solution first
""",
    "lecture": """
MODE — Lecture Q&A:
You act as a 24/7 office hours assistant.
- Explain concepts from the lecture notes clearly
- Use analogies and examples to make ideas accessible
- Connect ideas across different lectures when relevant
- If a concept isn't in the notes, say so and offer general guidance
""",
}


def build_system_prompt() -> str:
    """Build the complete system prompt for the Teaching Assistant."""

    prompt = f"""IDENTITY:
You are Spark, an AI Teaching Companion for "{Config.course_name}".
You help students learn by answering their spoken questions using course materials.

RULES:
- Keep responses SHORT (2-4 sentences) since this is voice conversation
- Be accurate — only use information from the provided course materials
- If you don't know or the materials don't cover it, say so honestly
- Never fabricate information about the course
- Speak naturally, as if talking to a student in office hours
- NO filler phrases ("Sure!", "Of course!", "I'd be happy to help!")
- Get straight to the answer
- CRITICAL: Your output is spoken aloud via text-to-speech. NEVER use:
  - Markdown formatting (no **, *, #, `, -, or bullet symbols)
  - Filenames or file extensions (say "the syllabus" not "syllabus.txt")
  - Special characters, code blocks, or lists with symbols
  - Write everything as plain conversational sentences
"""

    # Teaching style
    style = TEACHING_STYLES.get(Config.teaching_style, TEACHING_STYLES["supportive"])
    prompt += f"\n{style}\n"

    # Mode behavior
    mode_behavior = MODE_BEHAVIORS.get(Config.mode, MODE_BEHAVIORS["faq"])
    prompt += f"\n{mode_behavior}\n"

    # Custom educator instructions
    if Config.custom_instructions and Config.custom_instructions.strip():
        prompt += f"\nEDUCATOR INSTRUCTIONS:\n{Config.custom_instructions}\n"

    # Course materials context
    context = create_teaching_context(Config.mode)
    prompt += f"\n{context}\n"

    return prompt


def update_prompt_if_needed(context: LLMContext):
    """Update context's system prompt if config changed."""
    new_prompt = build_system_prompt()
    if context.messages and context.messages[0]["role"] == "system":
        context.messages[0]["content"] = new_prompt
        logger.info("System prompt updated")


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount UI
ui_path = Path(__file__).parent / "ui"
app.mount("/ui", StaticFiles(directory=ui_path), name="ui")


# ============================================================
# BOT PIPELINE
# ============================================================

async def run_bot(connection):
    """Create and run the Pipecat voice AI pipeline."""

    transport = SmallWebRTCTransport(
        webrtc_connection=connection,
        params=TransportParams(
            audio_out_enabled=True,
            audio_in_enabled=True,
            video_out_enabled=False,
            video_in_enabled=False,
            audio_out_sample_rate=24000,
            audio_in_sample_rate=16000,
        ),
    )

    # Speech-to-Text (Local Faster-Whisper, tiny model for speed)
    stt = WhisperSTTService(
        model="tiny",
        device="auto",
        no_speech_prob=0.4,
    )

    # LLM (Ollama local, streaming for sentence-by-sentence TTS)
    llm = OLLamaLLMService(
        model=os.getenv("LLM_MODEL", "gemma3:4b"),
        base_url=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/v1"),
        params=OLLamaLLMService.InputParams(
            temperature=Config.llm_params.get("temperature", 0.3),
            max_tokens=Config.llm_params.get("max_tokens", 150),
        ),
    )

    # Text-to-Speech (Kokoro local, 82M model)
    tts = KokoroTTSService(voice_id="af_heart")

    # Voice Activity Detection
    vad_analyzer = SileroVADAnalyzer(
        params=VADParams(
            stop_secs=0.3,
            start_secs=0.05,
            confidence=0.4,
            min_volume=0.2,
        )
    )
    vad = VADProcessor(vad_analyzer=vad_analyzer)

    # Context with system prompt
    messages = [{"role": "system", "content": build_system_prompt()}]
    context = LLMContext(messages)
    context_aggregator = LLMContextAggregatorPair(context)

    global global_context
    global_context = context

    sentence_aggregator = SentenceAggregator()
    tts_cleanup = TTSTextCleanup()

    runner = PipelineRunner()

    task = PipelineTask(
        pipeline=Pipeline([
            transport.input(),
            vad,
            stt,
            context_aggregator.user(),
            llm,
            sentence_aggregator,
            tts_cleanup,
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ]),
        params=PipelineParams(allow_interruptions=True),
    )

    # Speak the greeting when the client connects
    @transport.event_handler("on_client_connected")
    async def on_connected(transport, webrtc_connection):
        greeting = "Hello! I'm Spark, your AI Teaching Companion. Ask me anything about the course."
        await task.queue_frame(TTSSpeakFrame(text=greeting, append_to_context=True))

    await runner.run(task)


# ============================================================
# API ROUTES
# ============================================================

@app.get("/")
async def get_client():
    """Serve the main UI."""
    return FileResponse(ui_path / "index.html")


@app.get("/api/config")
async def get_config():
    """Return current configuration."""
    return {
        "mode": Config.mode,
        "teachingStyle": Config.teaching_style,
        "customInstructions": Config.custom_instructions,
        "courseName": Config.course_name,
        "llmParams": Config.llm_params,
        "modes": {k: v["label"] for k, v in MODES.items()},
        "materials": {k: get_loaded_files(k) for k in MODES},
    }


@app.post("/api/config")
async def update_config(request: Request):
    """Update configuration in real-time."""
    data = await request.json()

    if "mode" in data and data["mode"] in MODES:
        Config.mode = data["mode"]

    if "teachingStyle" in data and data["teachingStyle"] in TEACHING_STYLES:
        Config.teaching_style = data["teachingStyle"]

    if "customInstructions" in data:
        Config.custom_instructions = data["customInstructions"]

    if "courseName" in data:
        Config.course_name = data["courseName"]

    if "llmParams" in data:
        Config.llm_params.update(data["llmParams"])

    # Real-time prompt update
    if global_context:
        try:
            update_prompt_if_needed(global_context)
        except Exception as e:
            logger.error(f"Failed to update context: {e}")

    return {
        "status": "ok",
        "config": {
            "mode": Config.mode,
            "teachingStyle": Config.teaching_style,
            "courseName": Config.course_name,
        },
    }


@app.post("/api/materials/reload")
async def reload_course_materials():
    """Reload course materials from disk."""
    summary = reload_materials()
    return {
        "status": "ok",
        "materials": summary,
    }


@app.post("/api/offer")
async def sdp_offer(request: Request):
    """Handle WebRTC offer for voice connection."""
    data = await request.json()
    sdp = data["sdp"]
    type_ = data["type"]

    conn = SmallWebRTCConnection()
    await conn.initialize(sdp, type_)
    answer = conn.get_answer()

    asyncio.create_task(run_bot(conn))

    return answer


# ============================================================
# MAIN
# ============================================================

def check_ollama():
    """Pre-flight check: make sure Ollama is running before starting the bot."""
    import urllib.request
    import urllib.error

    ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/v1")
    base = ollama_url.rstrip("/").removesuffix("/v1")

    try:
        req = urllib.request.Request(f"{base}/api/version")
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                return True
    except Exception:
        pass

    # Fallback: try base URL (older Ollama versions)
    try:
        req = urllib.request.Request(base)
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                return True
    except Exception:
        pass

    return False


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("BOT_PORT", 7860))

    # Pre-flight: check Ollama
    if not check_ollama():
        logger.error("""
    ============================================================
      ERROR: Cannot reach Ollama!

      Ollama must be running before you start Spark.

      Fix:
        1. Open a NEW terminal window
        2. Run:  ollama serve
        3. Wait until you see "Listening on ..."
        4. Come back here and run:  python bot_teaching_assistant.py

      If Ollama is not installed, download it from:
        https://ollama.com
    ============================================================
        """)
        sys.exit(1)

    logger.info(f"""
    ============================================================

      SPARK — AI Teaching Companion
      AI PC for Educators — Building Teaching Assistants

      Open: http://localhost:{port}/

      Voice Pipeline:
      Mic (Whisper STT) -> LLM (Ollama) -> Speaker (Kokoro TTS)

    ============================================================
    """)

    uvicorn.run(app, host="127.0.0.1", port=port)
