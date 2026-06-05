# Spark — AI Teaching Companion

> **Activity: Building Teaching Assistants**
> Design simple agents that can handle academic research workflows.
>
> Part of the **AI PC for Educators** course module.

A voice-powered AI Teaching Companion that helps educators reduce repetitive workload. Students speak questions, the bot answers using your course materials — running 100% locally on your machine.

---

## What You Need

- **Python 3.10+** — [Download here](https://www.python.org/downloads/) (check "Add Python to PATH" during install)
- **Ollama** — [Download here](https://ollama.com)
- A working **microphone**
- **Chrome** or Edge browser
- ~5 GB free disk space (for AI models and dependencies)

---

## Setup

### Step 1 — Install Ollama

Download and install from [ollama.com](https://ollama.com), then pull the model:

```bash
ollama pull gemma3:4b
```

> First pull downloads ~2.5 GB. After that it's cached locally.

### Step 2 — Install Python Dependencies

Open a terminal in the project folder and run:

```bash
python -m venv venv
```

Activate the virtual environment:

```powershell
# Windows (PowerShell — default terminal)
.\venv\Scripts\Activate.ps1

# Windows (Command Prompt)
venv\Scripts\activate.bat

# macOS/Linux
source venv/bin/activate
```

> You should see `(venv)` at the start of your terminal prompt. If you don't, the activation didn't work — try the other command for your terminal type.

Then install dependencies:

```bash
pip install -r requirements.txt
```

### Step 3 — Configure (Optional)

Copy the example config:

```powershell
# Windows (PowerShell)
Copy-Item .env.example .env

# Windows (Command Prompt)
copy .env.example .env

# macOS/Linux
cp .env.example .env
```

Edit `.env` to customize:

```
OLLAMA_URL=http://127.0.0.1:11434/v1
LLM_MODEL=gemma3:4b
COURSE_NAME=Introduction to AI
DEFAULT_MODE=faq
BOT_PORT=7860
```

---

## Running

You need **two terminals** open at the same time.

### Terminal 1 — Start Ollama

```bash
ollama serve
```

> On Windows, Ollama may already be running in the background after installation. If you see "address already in use", that's fine — it means Ollama is already running and you can skip this step.

### Terminal 2 — Start the bot

Make sure you activate the virtual environment first:

```powershell
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Windows (Command Prompt)
venv\Scripts\activate.bat

# macOS/Linux
source venv/bin/activate
```

Then start the bot:

```bash
python bot_teaching_assistant.py
```

Open **http://localhost:7860** in your browser, click **Start Session**, and talk.

> The bot checks if Ollama is running at startup. If it's not, you'll see a clear error telling you to run `ollama serve` first.

---

## Architecture

```
Student speaks
      |
  [Microphone]     Browser (WebRTC)
      |
  [Silero VAD]     Voice Activity Detection
      |
  [Whisper STT]    Speech to Text (local, tiny model)
      |
  [Ollama LLM]     Gemma3 4B + Course Materials Context
      |
  [Kokoro TTS]     Text to Speech (local, 82M model)
      |
  [Speaker]        Student hears the answer
```

All processing happens on your machine. No data leaves your computer.

---

## Adding Your Course Materials

Delete the sample files in `course_materials/` and replace them with your own documents:

```
course_materials/
    |-- (root files)            --> Used in "Course FAQ" mode
    |   syllabus.txt
    |   policies.txt
    |
    |-- assignments/            --> Used in "Assignment Help" mode
    |   assignment1.txt
    |   rubric.pdf
    |
    |-- lectures/               --> Used in "Lecture Q&A" mode
        week1_intro.txt
        week2_algorithms.md
```

**Supported formats:** `.txt`, `.md`, `.pdf`, `.docx`

> `.pdf` and `.docx` require optional packages. Uncomment `PyPDF2` and `python-docx` in `requirements.txt` and run `pip install -r requirements.txt` again to enable them.

After adding files, click the reload button in the UI — no restart needed.

**Tips:**

- Keep files concise (the AI has a ~12,000 character context window per mode)
- Use descriptive filenames — the bot mentions document names in answers
- Plain text (`.txt`) works best for accuracy

---

## Three Modes

| Mode                | Purpose                      | Behavior                                    |
| ------------------- | ---------------------------- | ------------------------------------------- |
| **Course FAQ**      | Syllabus, policies, schedule | Answers logistical questions from root docs |
| **Assignment Help** | Guided homework support      | Gives hints, never gives direct answers     |
| **Lecture Q&A**     | 24/7 office hours            | Explains concepts from lecture notes        |

Switch modes using the right panel in the UI.

---

## Customization

### Teaching Styles

| Style          | Behavior                               |
| -------------- | -------------------------------------- |
| **Supportive** | Warm, encouraging, suggests next steps |
| **Socratic**   | Guides with questions, gives hints     |
| **Concise**    | Brief 1-2 sentence answers only        |

### Custom Instructions

In the Settings tab, add educator instructions like:

- "Always relate concepts to real-world examples"
- "Encourage students to visit office hours"
- "Focus on practical applications over theory"

### Environment Variables

Copy `.env.example` to `.env` and customize:

```
COURSE_NAME=Introduction to AI
DEFAULT_MODE=faq
LLM_MODEL=gemma3:4b
BOT_PORT=7860
```

---

## Testing

Run the diagnostic script to verify all services:

```bash
python test_services.py
```

**Note:** Both Ollama and the bot must be running for all tests to pass.

---

## Project Structure

```
Spark/
    |-- bot_teaching_assistant.py   # Main bot (run this)
    |-- knowledge_base.py           # Document loader & context injection
    |-- test_services.py            # Service diagnostics
    |-- requirements.txt            # Python dependencies
    |-- .env.example                # Environment template
    |
    |-- ui/
    |   |-- index.html              # Teaching Assistant UI
    |   |-- app.js                  # Frontend controller
    |   |-- rtvi-client.js          # RTVI protocol library
    |
    |-- course_materials/
        |-- README.md               # Instructions for educators
        |-- sample_syllabus.txt     # Sample FAQ content
        |-- assignments/
        |   |-- sample_assignment.txt
        |-- lectures/
            |-- sample_lecture_notes.txt
```

---

## Troubleshooting

| Problem               | Solution                                                        |
| --------------------- | --------------------------------------------------------------- |
| "Cannot reach Ollama" | Open another terminal and run `ollama serve`                    |
| "address already in use" | Ollama is already running — skip `ollama serve` and go to Terminal 2 |
| No microphone access  | Allow mic in browser (Chrome: click lock icon in address bar)   |
| Bot not responding    | Make sure `ollama serve` is still running in the other terminal |
| Slow first response   | Normal — model loads into memory on first query                 |
| No audio output       | Check speaker/headphone volume; try a different browser         |
| "Connection failed"   | Make sure port 7860 is not used by another app                  |
| Knowledge not loading | Check file extensions (.txt, .md only by default)               |
| PowerShell won't activate venv | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` then try again |

---

## How It Works (Technical)

1. **WebRTC** establishes a real-time audio connection between browser and server
2. **Silero VAD** detects when the user starts/stops speaking
3. **Faster-Whisper** (tiny model) transcribes speech to text locally
4. The transcription is added to an **LLM context** with the system prompt
5. The system prompt includes course materials loaded by `knowledge_base.py`
6. **Ollama** streams the LLM response token-by-token
7. **SentenceAggregator** buffers text into complete sentences
8. **Kokoro TTS** converts each sentence to audio
9. Audio streams back to the browser via WebRTC

The entire pipeline runs in ~700-1600ms end-to-end.
