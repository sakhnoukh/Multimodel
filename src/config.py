import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EXTRACTED_IMAGES_DIR = BASE_DIR / "extracted_images"
CHROMA_DB_DIR = BASE_DIR / "chroma_db"
DOCUMENT_STORE_PATH = BASE_DIR / "document_store.json"
PDF_REGISTRY_PATH = BASE_DIR / "pdf_registry.json"
SUMMARIES_DIR = BASE_DIR / "summaries"

SAMPLE_PDF_PATH = DATA_DIR / "sample_manual.pdf"

EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
CHROMA_COLLECTION_NAME = "multimodal_rag"
TOP_K_RESULTS = 3

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
SILICONFLOW_BASE_URL = "https://api.siliconflow.com/v1"
VLM_MODEL_NAME = "Qwen/Qwen3-VL-8B-Instruct"

VLM_SUMMARY_PROMPT = (
    "You are a technical documentation assistant. Describe this engineering diagram "
    "in detail, including any labels, components, connections, and flow shown. "
    "Be precise and thorough — this description will be used for semantic search retrieval."
)

PDF_SUMMARY_PROMPT = (
    "You are a technical documentation assistant. Summarize the following technical manual "
    "in well-structured markdown format. Use headers (##), bullet points, and tables where appropriate. "
    "Only include sections that are explicitly requested. Be factual and precise."
)

SUMMARY_MAX_TOKENS = 2048
