import uuid
import json
from pathlib import Path

from src.config import (
    SAMPLE_PDF_PATH,
    EXTRACTED_IMAGES_DIR,
    DOCUMENT_STORE_PATH,
)


def extract_pdf(pdf_path: Path = SAMPLE_PDF_PATH) -> list[dict]:
    """Extract text and images from a PDF using pymupdf.

    Returns a list of elements: {uuid, type, content, path, page}.
    """
    import fitz

    EXTRACTED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    text_elements = []
    image_elements = []

    for page_num in range(len(doc)):
        page = doc[page_num]

        # Extract text
        page_text = page.get_text("text").strip()
        if page_text:
            text_elements.append({
                "type": "text",
                "content": page_text,
                "path": None,
                "page": page_num + 1,
            })

        # Extract images
        image_list = page.get_images(full=True)
        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image.get("ext", "jpg")

            elem_id_placeholder = f"page{page_num + 1}_img{img_index}"
            img_path = EXTRACTED_IMAGES_DIR / f"{elem_id_placeholder}.jpg"

            # Convert to JPG if needed
            if image_ext.lower() not in ("jpg", "jpeg"):
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(image_bytes))
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(str(img_path), "JPEG", quality=95)
            else:
                img_path = EXTRACTED_IMAGES_DIR / f"{elem_id_placeholder}.{image_ext}"
                img_path.write_bytes(image_bytes)

            image_elements.append({
                "type": "image",
                "content": None,
                "path": str(img_path),
                "page": page_num + 1,
            })

    doc.close()

    # Assign UUIDs
    elements = []
    for te in text_elements:
        te["uuid"] = str(uuid.uuid4())
        elements.append(te)
    for ie in image_elements:
        ie["uuid"] = str(uuid.uuid4())
        elements.append(ie)

    _save_document_store(elements)
    _save_elements_json(elements)

    print(f"Extraction complete: {len(text_elements)} text chunks, {len(image_elements)} images")
    return elements


def _save_document_store(elements: list[dict]) -> None:
    """Save UUID → element mapping to document_store.json."""
    store = {}
    for elem in elements:
        store[elem["uuid"]] = {
            "type": elem["type"],
            "content": elem["content"],
            "path": elem["path"],
            "page": elem["page"],
        }
    DOCUMENT_STORE_PATH.write_text(json.dumps(store, indent=2, ensure_ascii=False))


def _save_elements_json(elements: list[dict]) -> None:
    """Save the full elements list for debugging."""
    output_path = EXTRACTED_IMAGES_DIR.parent / "extracted_elements.json"
    output_path.write_text(json.dumps(elements, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    extract_pdf()
