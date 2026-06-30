from typing import Generator

from src.config import (
    SILICONFLOW_API_KEY,
    SILICONFLOW_BASE_URL,
    VLM_MODEL_NAME,
)


def explain_stream(
    content_type: str,
    content: str,
    page: int,
    source_pdf: str,
) -> Generator[str, None, None]:
    """Stream a detailed explanation of a highlighted text excerpt or image region.

    Args:
        content_type: "text" or "image"
        content: highlighted text (for text) or base64-encoded JPEG (for image)
        page: PDF page number
        source_pdf: source PDF filename

    Yields: explanation text chunks
    """
    from openai import OpenAI

    client = OpenAI(api_key=SILICONFLOW_API_KEY, base_url=SILICONFLOW_BASE_URL)

    messages = _build_explanation_messages(content_type, content, page, source_pdf)

    stream = client.chat.completions.create(
        model=VLM_MODEL_NAME,
        messages=messages,
        max_tokens=1024,
        temperature=0.4,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content


def _build_explanation_messages(
    content_type: str,
    content: str,
    page: int,
    source_pdf: str,
) -> list[dict]:
    """Construct the multimodal message payload for explanation requests."""

    if content_type == "image":
        prompt_text = (
            f"You are a technical educator helping a student understand a technical manual. "
            f"The student selected a region of an image on page {page} of {source_pdf} that they find unclear. "
            f"Explain what is shown in this image region clearly and thoroughly. "
            f"Describe the components, their relationships, and how they work together. "
            f"Use simple language, analogies where helpful, and break down complex terms. "
            f"Format your response in markdown."
        )
        return [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{content}"
                        },
                    },
                ],
            }
        ]
    else:
        prompt_text = (
            f"You are a technical educator helping a student understand a technical manual. "
            f"The student highlighted the following excerpt from page {page} of {source_pdf}:\n\n"
            f"---\n{content}\n---\n\n"
            f"Explain this excerpt clearly and thoroughly. Make it easier to understand for someone "
            f"studying this material. Use simple language, analogies where helpful, and break down "
            f"complex terms. If the excerpt references figures or diagrams, explain what those would "
            f"typically show. Format your response in markdown."
        )
        return [
            {
                "role": "user",
                "content": prompt_text,
            }
        ]
