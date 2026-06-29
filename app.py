from pathlib import Path

import streamlit as st

from src.config import (
    DATA_DIR,
    SAMPLE_PDF_PATH,
    DOCUMENT_STORE_PATH,
    CHROMA_DB_DIR,
)
from src.extract import extract_pdf
from src.index import build_index
from src.retrieve import retrieve_and_answer_stream


st.set_page_config(
    page_title="Multimodal Support Engineer",
    page_icon="🔧",
    layout="wide",
)


# --- Sidebar: Pipeline Controls & Transparency ---
with st.sidebar:
    st.header("🔧 Pipeline Controls")

    # PDF upload
    uploaded_pdf = st.file_uploader(
        "Upload a technical PDF",
        type=["pdf"],
        help="Upload a PDF manual to ingest. Replaces the current sample PDF.",
    )
    if uploaded_pdf is not None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        save_path = DATA_DIR / "sample_manual.pdf"
        with open(save_path, "wb") as f:
            f.write(uploaded_pdf.getbuffer())
        st.success(f"Uploaded: {uploaded_pdf.name}")

    # Show PDF status
    if SAMPLE_PDF_PATH.exists():
        st.success(f"Current PDF: {SAMPLE_PDF_PATH.name}")
    else:
        st.warning("No PDF found. Upload one above.")

    # One-click pipeline: Extract + Index
    if st.button("Run Full Pipeline", help="Extract text/images and index in ChromaDB in one step"):
        if not SAMPLE_PDF_PATH.exists():
            st.error("Please upload a PDF first.")
        else:
            with st.spinner("Extracting text and images from PDF..."):
                try:
                    extract_pdf()
                    st.success("Extraction complete!")
                except Exception as e:
                    st.error(f"Extraction failed: {e}")

            with st.spinner("Generating VLM summaries and indexing in ChromaDB..."):
                try:
                    build_index()
                    st.success("Indexing complete! You can now ask questions.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Indexing failed: {e}")

    # Advanced: separate steps
    with st.expander("Advanced: Step-by-step"):
        if st.button("Run Extraction Only", help="Extract text and images from the PDF"):
            with st.spinner("Extracting..."):
                try:
                    extract_pdf()
                    st.success("Extraction complete!")
                except Exception as e:
                    st.error(f"Extraction failed: {e}")

        if st.button("Run Indexing Only", help="Generate VLM summaries and index in ChromaDB"):
            with st.spinner("Indexing..."):
                try:
                    build_index()
                    st.success("Indexing complete!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Indexing failed: {e}")

    st.divider()

    # Transparency: show retrieved sources
    st.header("📋 Retrieved Sources")
    if "last_retrieved_items" in st.session_state and st.session_state.last_retrieved_items:
        for i, item in enumerate(st.session_state.last_retrieved_items):
            type_label = "📝 Text" if item["type"] == "text" else "🖼️ Image"
            with st.expander(f"{type_label} — Page {item['page']} (score: {1 - item['distance']:.2%})"):
                if item["type"] == "text":
                    st.text(item["content"][:500] + ("..." if len(item["content"]) > 500 else ""))
                elif item["type"] == "image":
                    if item.get("path") and Path(item["path"]).exists():
                        st.image(item["path"], caption=f"Page {item['page']}")
                    st.caption(f"VLM Summary: {item['content'][:200]}...")
    else:
        st.info("Retrieved sources will appear here after you ask a question.")


# --- Main: Chat Interface ---
st.title("🔧 Multimodal Support Engineer")
st.markdown(
    "Ask questions about technical manuals. The system retrieves relevant "
    "text excerpts **and engineering diagrams** to answer your query."
)

# Check if pipeline has been run
pipeline_ready = DOCUMENT_STORE_PATH.exists() and CHROMA_DB_DIR.exists()

if not pipeline_ready:
    st.info(
        "👆 Upload a PDF in the sidebar and click **Run Full Pipeline** to get started."
    )

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "images" in message:
            for img_path in message["images"]:
                st.image(img_path, width=400)

# Chat input
if prompt := st.chat_input("Ask a question about the manual..."):
    if not pipeline_ready:
        st.error("Pipeline not ready. Run extraction and indexing first.")
    else:
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Retrieve and stream answer
        with st.chat_message("assistant"):
            with st.spinner("Retrieving relevant context..."):
                retrieved_items, stream = retrieve_and_answer_stream(prompt)

            # Store retrieved items for sidebar transparency
            st.session_state.last_retrieved_items = retrieved_items

            # Stream the answer
            full_response = st.write_stream(stream)

            # Show retrieved images inline
            image_paths = []
            for item in retrieved_items:
                if item["type"] == "image" and item.get("path") and Path(item["path"]).exists():
                    st.image(item["path"], caption=f"Retrieved diagram (page {item['page']})", width=400)
                    image_paths.append(item["path"])

        st.session_state.messages.append({
            "role": "assistant",
            "content": full_response,
            "images": image_paths,
        })
