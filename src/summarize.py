import json
from pathlib import Path
from typing import Callable, Optional

from src.config import (
    DOCUMENT_STORE_PATH,
    SUMMARIES_DIR,
    PDF_REGISTRY_PATH,
    PDF_SUMMARY_PROMPT,
    SILICONFLOW_API_KEY,
    SILICONFLOW_BASE_URL,
    VLM_MODEL_NAME,
    SUMMARY_MAX_TOKENS,
)

ProgressCallback = Optional[Callable[[int, int, str], None]]

FOCUS_SECTIONS = {
    "overview": "## Overview\nWhat this manual is about, its target audience, and scope. 1-2 paragraphs.",
    "topics": "## Key Topics\nTable of contents or list of main sections/topics covered in the manual.",
    "components": "## Components & Specifications\nKey components, parts, specifications, and technical details mentioned in the manual.",
    "safety": "## Safety & Warnings\nNotable safety instructions, warnings, and critical procedures from the manual.",
}

MAX_TEXT_CHARS = 60000


def generate_pdf_summary(
    pdf_name: str,
    focus_areas: list[str] | None = None,
    custom_instructions: str = "",
    progress_callback: ProgressCallback = None,
) -> str:
    """Generate a markdown summary for a PDF using the VLM.

    Args:
        pdf_name: Name of the PDF (as stored in registry).
        focus_areas: List of focus keys from FOCUS_SECTIONS (default: all).
        custom_instructions: Optional free-text focus from the user.
        progress_callback: Optional callback(current, total, message).

    Returns:
        The generated markdown summary string.
    """
    if focus_areas is None:
        focus_areas = list(FOCUS_SECTIONS.keys())

    if not DOCUMENT_STORE_PATH.exists():
        raise FileNotFoundError("document_store.json not found. Ingest a PDF first.")

    store: dict = json.loads(DOCUMENT_STORE_PATH.read_text())

    # Gather text chunks for this PDF, sorted by page
    text_entries = [
        (entry["page"], entry["content"])
        for entry in store.values()
        if entry.get("source_pdf") == pdf_name and entry["type"] == "text" and entry.get("content")
    ]
    text_entries.sort(key=lambda x: x[0])

    if not text_entries:
        raise ValueError(f"No text content found for {pdf_name}. Has it been ingested?")

    full_text = "\n\n".join(content for _, content in text_entries)
    if len(full_text) > MAX_TEXT_CHARS:
        full_text = full_text[:MAX_TEXT_CHARS] + "\n\n[... text truncated due to length ...]"

    # Build prompt — case-insensitive match for legacy keys, generic fallback for new ones
    focus_lower = {k.lower(): k for k in FOCUS_SECTIONS}
    section_parts: list[str] = []
    for area in focus_areas:
        legacy_key = focus_lower.get(area.lower())
        if legacy_key:
            section_parts.append(f"- {FOCUS_SECTIONS[legacy_key]}")
        else:
            section_parts.append(
                f"- ## {area}\nSummarize the {area.lower()} from the document."
            )
    section_instructions = "\n".join(section_parts)
    if not section_instructions:
        section_instructions = f"- {FOCUS_SECTIONS['overview']}"

    prompt = f"{PDF_SUMMARY_PROMPT}\n\nInclude the following sections:\n{section_instructions}"
    if custom_instructions.strip():
        prompt += f"\n\nAdditional instructions from the user:\n{custom_instructions.strip()}"
    prompt += f"\n\n--- MANUAL TEXT ---\n{full_text}"

    if progress_callback:
        progress_callback(0, 1, f"Generating summary for {pdf_name}...")

    # Call VLM
    from openai import OpenAI
    client = OpenAI(api_key=SILICONFLOW_API_KEY, base_url=SILICONFLOW_BASE_URL)

    response = client.chat.completions.create(
        model=VLM_MODEL_NAME,
        messages=[
            {"role": "user", "content": prompt},
        ],
        max_tokens=SUMMARY_MAX_TOKENS,
        temperature=0.3,
    )

    summary = response.choices[0].message.content.strip()

    # Save to file
    SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = pdf_name.replace(" ", "_").replace(".pdf", "")
    summary_path = SUMMARIES_DIR / f"{safe_name}.md"
    summary_path.write_text(summary)

    # Update registry
    _update_registry_summary(pdf_name, str(summary_path))

    if progress_callback:
        progress_callback(1, 1, f"Summary saved for {pdf_name}.")

    return summary


def get_summary(pdf_name: str) -> str | None:
    """Return the markdown summary for a PDF, or None if not found."""
    safe_name = pdf_name.replace(" ", "_").replace(".pdf", "")
    summary_path = SUMMARIES_DIR / f"{safe_name}.md"
    if summary_path.exists():
        return summary_path.read_text()
    return None


def delete_summary(pdf_name: str) -> None:
    """Delete the summary file for a PDF and update the registry."""
    safe_name = pdf_name.replace(" ", "_").replace(".pdf", "")
    summary_path = SUMMARIES_DIR / f"{safe_name}.md"
    if summary_path.exists():
        summary_path.unlink()

    registry = _load_registry()
    if pdf_name in registry:
        registry[pdf_name].pop("has_summary", None)
        registry[pdf_name].pop("summary_path", None)
        PDF_REGISTRY_PATH.write_text(json.dumps(registry, indent=2))


def _update_registry_summary(pdf_name: str, summary_path: str) -> None:
    registry = _load_registry()
    if pdf_name not in registry:
        registry[pdf_name] = {"active": True, "element_count": 0}
    registry[pdf_name]["has_summary"] = True
    registry[pdf_name]["summary_path"] = summary_path
    PDF_REGISTRY_PATH.write_text(json.dumps(registry, indent=2))


def list_summaries() -> list[str]:
    """Return a list of PDF names that have summaries."""
    registry = _load_registry()
    return [name for name, info in registry.items() if info.get("has_summary")]


def regenerate_summary_with_feedback(
    pdf_name: str,
    feedback: str,
) -> str:
    """Regenerate a PDF summary incorporating user feedback.

    Takes the existing summary, the original PDF text, and the user's feedback
    to produce an improved summary. The old summary file is replaced.

    Args:
        pdf_name: Name of the PDF (as stored in registry).
        feedback: User's feedback on what to change/improve.

    Returns:
        The regenerated markdown summary string.
    """
    existing_summary = get_summary(pdf_name)
    if existing_summary is None:
        raise FileNotFoundError(f"No existing summary found for {pdf_name}.")

    if not DOCUMENT_STORE_PATH.exists():
        raise FileNotFoundError("document_store.json not found. Ingest a PDF first.")

    store: dict = json.loads(DOCUMENT_STORE_PATH.read_text())

    text_entries = [
        (entry["page"], entry["content"])
        for entry in store.values()
        if entry.get("source_pdf") == pdf_name and entry["type"] == "text" and entry.get("content")
    ]
    text_entries.sort(key=lambda x: x[0])

    if not text_entries:
        raise ValueError(f"No text content found for {pdf_name}. Has it been ingested?")

    full_text = "\n\n".join(content for _, content in text_entries)
    if len(full_text) > MAX_TEXT_CHARS:
        full_text = full_text[:MAX_TEXT_CHARS] + "\n\n[... text truncated due to length ...]"

    prompt = (
        f"{PDF_SUMMARY_PROMPT}\n\n"
        f"The user has reviewed the current summary and provided the following feedback. "
        f"Regenerate the summary in full, incorporating this feedback while remaining "
        f"factual and grounded in the source text.\n\n"
        f"--- CURRENT SUMMARY ---\n{existing_summary}\n\n"
        f"--- USER FEEDBACK ---\n{feedback.strip()}\n\n"
        f"--- MANUAL TEXT ---\n{full_text}"
    )

    from openai import OpenAI
    client = OpenAI(api_key=SILICONFLOW_API_KEY, base_url=SILICONFLOW_BASE_URL)

    response = client.chat.completions.create(
        model=VLM_MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=SUMMARY_MAX_TOKENS,
        temperature=0.3,
    )

    summary = response.choices[0].message.content.strip()

    SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = pdf_name.replace(" ", "_").replace(".pdf", "")
    summary_path = SUMMARIES_DIR / f"{safe_name}.md"
    summary_path.write_text(summary)

    _update_registry_summary(pdf_name, str(summary_path))

    return summary


def chat_with_summary_stream(summary_text: str, question: str, history: list[dict] | None = None):
    """Stream a VLM answer to a question, using the summary as context.

    Args:
        summary_text: The markdown summary to use as context.
        question: The user's question.
        history: Optional list of {"role": "user"/"assistant", "content": str} messages.

    Yields:
        Token chunks from the VLM stream.
    """
    from openai import OpenAI
    client = OpenAI(api_key=SILICONFLOW_API_KEY, base_url=SILICONFLOW_BASE_URL)

    system_prompt = (
        "You are a technical documentation assistant. The user has generated a summary "
        "of a technical manual. Answer the user's questions based on the summary below. "
        "If the answer is not contained in the summary, say so clearly.\n\n"
        f"--- SUMMARY ---\n{summary_text}"
    )

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": question})

    stream = client.chat.completions.create(
        model=VLM_MODEL_NAME,
        messages=messages,
        max_tokens=SUMMARY_MAX_TOKENS,
        temperature=0.3,
        stream=True,
    )

    for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def _load_registry() -> dict:
    if PDF_REGISTRY_PATH.exists():
        return json.loads(PDF_REGISTRY_PATH.read_text())
    return {}
