"""
Knowledge Base Module for AI Teaching Assistant
================================================

Loads course materials from the course_materials/ directory and provides
context injection for three teaching modes:

  - FAQ:        Root-level files (syllabus, policies, etc.)
  - Assignment: Files in assignments/ subfolder
  - Lecture:    Files in lectures/ subfolder

Supported formats: .txt, .md, .pdf, .docx
"""

import os
from pathlib import Path
from typing import Dict, List
from loguru import logger

# Base directory for course materials
COURSE_MATERIALS_DIR = Path(__file__).parent / "course_materials"

# Maximum characters of context to inject per mode (~12,000 chars)
MAX_CONTEXT_CHARS = 12000

# Supported file extensions
SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}

# Teaching modes and their source directories
MODES = {
    "faq": {
        "label": "Course FAQ",
        "description": "Syllabus, policies, schedule",
        "path": None,  # Root-level files only
    },
    "assignment": {
        "label": "Assignment Help",
        "description": "Guided homework support",
        "path": "assignments",
    },
    "lecture": {
        "label": "Lecture Q&A",
        "description": "24/7 office hours",
        "path": "lectures",
    },
}


def _read_txt(file_path: Path) -> str:
    """Read plain text or markdown file."""
    try:
        return file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"Failed to read {file_path}: {e}")
        return ""


def _read_pdf(file_path: Path) -> str:
    """Read PDF file. Requires PyPDF2 or falls back gracefully."""
    try:
        import PyPDF2
        text = ""
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() or ""
        return text
    except ImportError:
        logger.warning(f"PyPDF2 not installed, skipping PDF: {file_path.name}")
        return f"[PDF file: {file_path.name} - install PyPDF2 to read]"
    except Exception as e:
        logger.warning(f"Failed to read PDF {file_path}: {e}")
        return ""


def _read_docx(file_path: Path) -> str:
    """Read DOCX file. Requires python-docx or falls back gracefully."""
    try:
        import docx
        doc = docx.Document(str(file_path))
        return "\n".join(p.text for p in doc.paragraphs)
    except ImportError:
        logger.warning(f"python-docx not installed, skipping DOCX: {file_path.name}")
        return f"[DOCX file: {file_path.name} - install python-docx to read]"
    except Exception as e:
        logger.warning(f"Failed to read DOCX {file_path}: {e}")
        return ""


def read_file(file_path: Path) -> str:
    """Read a file based on its extension."""
    ext = file_path.suffix.lower()
    if ext in (".txt", ".md"):
        return _read_txt(file_path)
    elif ext == ".pdf":
        return _read_pdf(file_path)
    elif ext == ".docx":
        return _read_docx(file_path)
    return ""


def get_files_for_mode(mode: str) -> List[Path]:
    """Get all supported files for a given teaching mode."""
    if mode not in MODES:
        mode = "faq"

    base = COURSE_MATERIALS_DIR
    if not base.exists():
        logger.warning(f"Course materials directory not found: {base}")
        return []

    subdir = MODES[mode]["path"]

    if subdir is None:
        # FAQ mode: only root-level files (not in subdirectories)
        # Exclude README.md — it's instructions for educators, not course content
        files = [
            f for f in base.iterdir()
            if f.is_file()
            and f.suffix.lower() in SUPPORTED_EXTENSIONS
            and f.name.lower() != "readme.md"
        ]
    else:
        target = base / subdir
        if not target.exists():
            logger.info(f"Subdirectory not found: {target}")
            return []
        files = [
            f for f in target.rglob("*")
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
        ]

    return sorted(files, key=lambda f: f.name)


def load_context(mode: str) -> str:
    """
    Load all course materials for a mode and return as a single context string.
    Truncates to MAX_CONTEXT_CHARS.
    """
    files = get_files_for_mode(mode)
    if not files:
        return ""

    parts = []
    total_len = 0

    for file_path in files:
        content = read_file(file_path).strip()
        if not content:
            continue

        header = f"--- {file_path.name} ---"
        section = f"{header}\n{content}\n"

        if total_len + len(section) > MAX_CONTEXT_CHARS:
            remaining = MAX_CONTEXT_CHARS - total_len
            if remaining > 100:
                parts.append(section[:remaining] + "\n[...truncated]")
            break

        parts.append(section)
        total_len += len(section)

    return "\n".join(parts)


def get_loaded_files(mode: str) -> List[str]:
    """Return list of filenames loaded for a mode (for UI display)."""
    return [f.name for f in get_files_for_mode(mode)]


def create_teaching_context(mode: str) -> str:
    """
    Create the context block that gets injected into the LLM system prompt.
    """
    context = load_context(mode)
    mode_info = MODES.get(mode, MODES["faq"])

    if not context:
        return f"""
COURSE MATERIALS ({mode_info['label']}):
No materials loaded. The educator hasn't added documents yet.
Answer general questions using your training knowledge,
but let the student know that specific course materials aren't available yet.
"""

    return f"""
COURSE MATERIALS ({mode_info['label']}):
The following documents have been provided by the educator.
Use ONLY this information to answer questions. If the answer isn't
in the materials, say so honestly.

{context}
"""


def reload_materials() -> Dict[str, List[str]]:
    """
    Reload and return summary of all available materials per mode.
    Useful for the UI reload button.
    """
    summary = {}
    for mode_key in MODES:
        files = get_loaded_files(mode_key)
        summary[mode_key] = files
        logger.info(f"  [{mode_key}] {len(files)} files: {files}")
    return summary


# Print summary on import
if COURSE_MATERIALS_DIR.exists():
    logger.info(f"Course materials directory: {COURSE_MATERIALS_DIR}")
    reload_materials()
else:
    logger.warning(f"No course_materials/ directory found. Create it and add your documents.")
