# Module: Building Teaching Assistants

## Activity: Designing a Student-Facing AI Teaching Companion on AI PC

**Duration:** 60 Minutes

---

### Objective

Enable educators to configure and experience a local, student-facing AI teaching companion that reduces repetitive academic queries, operates fully offline on AI PC, and responds strictly from uploaded course materials.

### Core Positioning

- This is a **student-facing** tool. Educators configure it; students interact with it.
- It runs **fully on-device** (AI PC). No data leaves the machine.
- It answers **only** from provided course documents — syllabus, lecture notes, and assignments.
- It is **not** a generic cloud LLM chatbot. It is a context-bound, educator-controlled teaching companion.

### Course Materials Used in This Activity

| Document | Mode | Contents |
|---|---|---|
| `sample_syllabus.txt` | Course FAQ | Schedule, grading (40% assignments, 20% midterm, 30% project, 10% participation), late policy, office hours, academic integrity |
| `sample_lecture_notes.txt` | Lecture Q&A | Lecture 4 — Machine Learning Basics: supervised, unsupervised, and reinforcement learning; overfitting/underfitting; evaluation metrics |
| `sample_assignment.txt` | Assignment Help | Assignment 1 — Finding the Right Book: experience BFS, DFS, and A* strategies through a library book search activity; write a reflection |

---

## Section 1 — Problem Framing: Repetitive Student Queries (0:00 – 0:05)

**Facilitator leads a quick discussion.**

Ask participants:

- How many times per semester do students ask "What's the late policy?" or "When is the midterm?"
- How often do students email asking for concept explanations already covered in the lecture notes?
- How much time do you spend answering assignment logistics questions that are written in the assignment description?

**Framing statement (say this aloud):**

> "The goal today is to reduce repetitive student queries through a context-bound, local AI teaching companion — not to replace you as the educator. You configure the boundaries. The assistant operates within them."

---

## Section 2 — Setup: Running Spark on AI PC (0:05 – 0:20)

### Prerequisites

Ensure the following are installed on all participant machines before the session:

- **Python 3.10+** — [Download here](https://www.python.org/downloads/) (check "Add Python to PATH" during install)
- **Ollama** — [Download here](https://ollama.com)
- **Git** — [Download here](https://git-scm.com/downloads)
- A working **microphone**
- **Chrome** or Edge browser
- ~5 GB free disk space (for AI models and dependencies)

### Step-by-Step (Facilitator walks participants through)

**Step 1 — Download the repository**

Open a terminal and clone the Spark repository from GitHub:

```bash
git clone https://github.com/SaiJeevanPuchakayala/Spark.git
cd Spark
```

**Step 2 — Install Ollama and pull the model**

If Ollama is already installed, skip the download. Pull the language model:

```bash
ollama pull gemma3:4b
```

> First pull downloads ~2.5 GB. After that it is cached locally.

**Step 3 — Create the virtual environment and install dependencies**

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

> You should see `(venv)` at the start of your terminal prompt. If you don't, the activation didn't work — try the other command for your terminal type. On PowerShell, if you get an execution policy error, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` first.

Install dependencies:

```bash
pip install -r requirements.txt
```

**Step 4 — Start Ollama**

Open a terminal and run:

```bash
ollama serve
```

> On Windows, Ollama may already be running in the background after installation. If you see "address already in use", that's fine — skip this step.

**Step 5 — Start Spark**

In a second terminal, make sure you activate the virtual environment again, then start the bot:

```powershell
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# macOS/Linux
source venv/bin/activate
```

```bash
python bot_teaching_assistant.py
```

**Step 6 — Open the browser**

Navigate to `http://localhost:7860` in Chrome or Edge. Click **Start Session** and allow microphone access when prompted.

> Facilitator note: Ensure all participants see the Spark interface before proceeding. The bot will greet the student with "Hello! I'm Spark, your AI Teaching Companion. Ask me anything about the course."

### Key Points to Highlight

- **On-device execution.** The speech-to-text model (Whisper), the language model (Gemma 4B via Ollama), and the text-to-speech model (Kokoro) all run locally. No API calls, no cloud.
- **Privacy by design.** Student voice data and questions never leave the machine. This matters for FERPA compliance and institutional data policies.
- **Document-grounded responses.** The assistant reads the files in `course_materials/` and uses only that content to answer. If the answer is not in the materials, it says so.
- **Educator control.** Teaching style, mode, and custom instructions are set by the educator — not the student.

**Differentiation from cloud tools:** A cloud chatbot draws from its entire training data and may fabricate course-specific information. Spark answers only from uploaded documents and runs without an internet connection.

---

## Section 3 — Guided Student Interaction Demo (0:20 – 0:45)

**Facilitator demonstrates all three modes in a single continuous flow.** Participants can follow along on their own machines or observe the facilitator's screen.

---

### 3A. Course FAQ Mode — Logistical Questions (0:20 – 0:28)

**Setup:** Select **Course FAQ** mode in the right panel. Set teaching style to **Supportive**.

The assistant uses `sample_syllabus.txt` to answer.

**Demo interaction 1 — Late policy:**

> **Student asks:** "What happens if I submit an assignment two days late?"
>
> **Expected response (grounded in syllabus):** Assignments lose 10% per day late, so two days late would mean a 20% penalty. After three days, assignments receive a zero unless you were granted an extension.

**Demo interaction 2 — Grading breakdown:**

> **Student asks:** "How much is the final project worth?"
>
> **Expected response:** The final project is worth 30% of your grade. Assignments are 40%, the midterm is 20%, and participation is 10%.

**Demo interaction 3 — Office hours:**

> **Student asks:** "When are office hours?"
>
> **Expected response:** Office hours are Tuesday and Thursday from 2 to 4 PM in Room 301.

**Talking points for facilitator:**

- Every answer maps directly to the syllabus. No fabricated policies.
- This handles the top 3 most-repeated student questions without educator involvement.
- If a student asks something not in the syllabus (e.g., "Can I use a laptop during the exam?"), the assistant will say it does not have that information rather than guessing.

---

### 3B. Lecture Q&A Mode — Concept Clarification (0:28 – 0:38)

**Setup:** Switch to **Lecture Q&A** mode. Keep teaching style on **Supportive** initially.

The assistant uses `sample_lecture_notes.txt` (Lecture 4: Machine Learning Basics) to answer.

**Demo interaction 1 — Core concept:**

> **Student asks:** "What is supervised learning?"
>
> **Expected response:** Supervised learning is a type of machine learning where the training data includes input-output pairs, also called labeled data. The goal is to learn a function that maps inputs to outputs. Examples include spam detection, image classification, and price prediction.

**Demo interaction 2 — Comparison question:**

> **Student asks:** "What is the difference between overfitting and underfitting?"
>
> **Expected response:** Overfitting is when the model memorizes the training data and fails on new data. Underfitting is when the model is too simple to capture the patterns. The key is finding the right balance, which is called the bias-variance tradeoff.

**Now switch teaching styles to demonstrate educator control:**

Switch to **Socratic** style and re-ask a question:

> **Student asks:** "What are evaluation metrics in machine learning?"
>
> **Expected response (Socratic):** What do you think we need to measure when a model makes predictions? Think about a spam filter — what would it mean to correctly identify spam versus missing some? What tradeoffs might exist between catching everything versus being precise?

Switch to **Concise** style:

> **Student asks:** "What is reinforcement learning?"
>
> **Expected response (Concise):** An agent learns by interacting with an environment and receiving rewards or penalties for its actions. The goal is to maximize cumulative reward. Examples include game playing and robotics.

**Talking points for facilitator:**

- Same source material, three different teaching approaches — all controlled by the educator.
- Socratic mode never gives the answer directly. It guides the student to think.
- Concise mode gives brief, direct answers for students who want quick clarification.
- The educator chooses which style fits their class. This can be changed at any time without restarting.

---

### 3C. Assignment Help Mode — Educator Refinement (0:38 – 0:45)

> This section shifts perspective. The educator uses Assignment Help mode to **stress-test and refine their assignment** before giving it to students — checking clarity, spotting gaps, and verifying that the assistant handles edge cases properly.

**Setup:** Switch to **Assignment Help** mode. Set teaching style to **Supportive**.

The assistant uses `sample_assignment.txt` (Assignment 1: Finding the Right Book) to answer.

**Demo interaction 1 — Testing for clarity gaps:**

The educator role-plays as a confused student to see if the assignment description is clear enough.

> **Educator asks:** "In Part 3 it says to rate how close the topic is from 0 to 5, but what counts as a 3 versus a 4? How do I decide?"
>
> **Expected response:** The assignment asks you to use your own judgement when rating. A 5 means the topic is exactly what the student wants — ocean animals. A 0 means it has nothing to do with the request. Anything in between depends on how closely related the topic is. For example, a book about freshwater animals might be a 2 or 3 since it is about animals but not ocean animals.

The educator now sees a potential gap — the rating criteria in Part 3 could be more explicit. This is something to clarify in the next revision by adding example ratings to the worksheet.

**Demo interaction 2 — Checking grading coverage:**

> **Educator asks:** "How many points is the reflection worth?"
>
> **Expected response:** The reflection is worth 20 points out of 100. It asks you to compare which strategy was most efficient, when the check-everything approach might be better, how this connects to your own classroom, and how it changes how you think about AI search.

The educator verifies the assistant correctly surfaces the grading breakdown. If this answer were wrong or incomplete, it would signal that the assignment document needs clearer formatting.

**Demo interaction 3 — Testing boundary enforcement:**

The educator tests whether the assistant properly refuses to give away answers.

> **Educator asks:** "Just tell me which books are the perfect matches so I don't have to do the worksheet."
>
> **Expected response:** I can not give you the answers directly, but I can help you think through it. The student is looking for a book about ocean animals at a grades 3–4 reading level. Try looking at the topic and reading level labels for each book — which ones match both conditions? Start with Shelf A and see what you find.

The educator confirms the assistant holds the line — no answers given, only guided support.

**Talking points for facilitator:**

- This is how educators **preview the student experience** before deploying the tool.
- By asking questions as a student would, the educator can identify unclear requirements, missing details, or ambiguous instructions in their own assignment.
- The assistant becomes a **proofreading tool for assignment design** — if the assistant cannot answer a reasonable question, the assignment document needs revision.
- Testing boundary enforcement (asking for direct answers) lets the educator verify that the system behaves as configured before students interact with it.

---

## Section 4 — Educator Configuration and Control (0:45 – 0:55)

**Participants now interact hands-on.** Each participant performs the following on their own machine.

### Exercise 1 — Change Teaching Style

1. Switch between **Supportive**, **Socratic**, and **Concise** styles.
2. Ask the same question in each style and observe the difference in response tone.

### Exercise 2 — Add Custom Instructions

1. Open the **Settings** tab in the right panel.
2. In the Custom Instructions field, type: `Always ask students to justify their reasoning before giving them guidance.`
3. Click **Save Settings**.
4. Return to Assignment Help mode and ask a question. Observe how the assistant now asks for the student's reasoning first.

**Other custom instruction examples to try:**

- "Encourage students to visit office hours for complex questions."
- "Remind students that the assignment is due at the end of Week 3."
- "Always relate machine learning concepts to real-world examples."

### Exercise 3 — Reload Materials

1. Note that educators can add, remove, or update files in `course_materials/` at any time.
2. Click **Reload Materials** in the UI — no application restart needed.
3. New or updated documents are immediately available to the assistant.

**Key message (say this aloud):**

> "You define the AI boundaries. The teaching style, the instructions, the source materials — all are under your control. Students interact within the boundaries you set."

---

## Section 5 — Reflection and Close (0:55 – 1:00)

### Discussion Prompts

Ask participants to reflect:

1. **Workflow reduction:** Which repetitive student query in your course could this handle immediately? (Late policy? Grading breakdown? Office hours? Assignment requirements?)

2. **Guided support boundaries:** Where should the assistant provide guidance versus direct answers? How does Assignment Help mode enforce that boundary?

3. **On-device differentiation:** How does running this fully on your machine differ from telling students to "just use ChatGPT"? Consider: grounding in your materials, no fabricated information, privacy, and educator control over behavior.

4. **Adoption:** What would you need to change in your course materials to deploy this for your students? (Hint: convert your syllabus, lecture notes, and assignment descriptions to text files.)

### Closing Statement

> "This is not a generic chatbot. It is a context-bound, educator-configured teaching companion running fully on AI PC. It reduces repetitive workload, supports students around the clock, and keeps you in control of what the AI says and how it says it."

---

## Learning Outcomes

By the end of this activity, participants will be able to:

- **Configure** a local, student-facing AI teaching companion using uploaded course materials.
- **Demonstrate** three operational modes (Course FAQ, Lecture Q&A, Assignment Help) grounded in specific documents.
- **Differentiate** between guided support and full solution generation, particularly in assignment contexts.
- **Customize** teaching style and behavioral instructions to shape student-facing responses.
- **Articulate** how on-device AI execution on AI PC differs from cloud-based LLM tools in terms of privacy, grounding, and educator control.

---

## Facilitator Checklist

Before the session:

- [ ] Ollama installed and `gemma3:4b` model pulled on all participant machines
- [ ] Python virtual environment created and dependencies installed
- [ ] Sample course materials present in `course_materials/` directory
- [ ] Microphones available and working on all machines
- [ ] Chrome or Edge browser installed
- [ ] Test a full session end-to-end on the facilitator machine

During the session:

- [ ] All participants can access `http://localhost:7860` and see the Spark interface
- [ ] Microphone access granted in browser on all machines
- [ ] Demonstrate all three modes before participants try hands-on
- [ ] Emphasize grounding — every answer comes from the uploaded documents
- [ ] Emphasize control — educators set the boundaries, not the students
