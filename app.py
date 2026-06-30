import json
from pathlib import Path

import streamlit as st

from src.config import (
    DATA_DIR,
    DOCUMENT_STORE_PATH,
    CHROMA_DB_DIR,
    PDF_REGISTRY_PATH,
    SUMMARIES_DIR,
)
from src.extract import extract_pdf, remove_pdf, get_pdf_registry
from src.index import build_index, incremental_index
from src.retrieve import retrieve_and_answer_stream
from src.summarize import generate_pdf_summary, get_summary, delete_summary, list_summaries, chat_with_summary_stream


def load_registry() -> dict:
    if PDF_REGISTRY_PATH.exists():
        return json.loads(PDF_REGISTRY_PATH.read_text())
    return {}


def save_registry(registry: dict) -> None:
    PDF_REGISTRY_PATH.write_text(json.dumps(registry, indent=2))


st.set_page_config(
    page_title="Multimodal Support Engineer",
    page_icon="🔧",
    layout="wide",
)


# --- Sidebar: Pipeline Controls & Transparency ---
with st.sidebar:
    st.header("🔧 Pipeline Controls")

    # Multi-PDF upload
    uploaded_files = st.file_uploader(
        "Upload technical PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        help="Upload one or more PDF manuals. New PDFs are processed automatically.",
    )
    if uploaded_files:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        registry = load_registry()

        # Save uploaded files and identify which are new
        new_pdfs = []
        existing_pdfs = []
        for uploaded in uploaded_files:
            save_path = DATA_DIR / uploaded.name
            with open(save_path, "wb") as f:
                f.write(uploaded.getbuffer())
            if uploaded.name in registry:
                existing_pdfs.append(uploaded.name)
            else:
                new_pdfs.append(uploaded.name)

        if new_pdfs:
            # --- Auto-ingest new PDFs with progress bar ---
            total_steps = len(new_pdfs) + 1  # extraction per PDF + indexing
            current_step = 0
            progress_bar = st.progress(0.0)
            status_text = st.empty()

            def update_progress(current, total, message):
                if total > 0:
                    frac = (current_step + current / total) / total_steps
                    progress_bar.progress(min(frac, 1.0))
                status_text.text(message)

            # Phase 1: Extract each new PDF
            for pdf_name in new_pdfs:
                current_step += 1
                pdf_path = DATA_DIR / pdf_name
                progress_bar.progress(current_step / total_steps)
                status_text.text(f"Extracting text and images from {pdf_name}...")
                try:
                    extract_pdf(pdf_path)
                except Exception as e:
                    st.error(f"Extraction failed for {pdf_name}: {e}")
                    progress_bar.empty()
                    status_text.empty()
                    st.rerun()

            # Phase 2: Incremental index (VLM summaries + embeddings for new elements)
            status_text.text("Generating VLM summaries and indexing new content...")
            try:
                new_count = incremental_index(progress_callback=update_progress)
                progress_bar.progress(1.0)
                if new_count > 0:
                    status_text.text(f"Done! Indexed {new_count} new elements from {len(new_pdfs)} PDF(s).")
                else:
                    status_text.text("No new elements to index.")
                st.success(f"Processed {len(new_pdfs)} new PDF(s)! Ready to query.")
            except Exception as e:
                st.error(f"Indexing failed: {e}")
            finally:
                progress_bar.empty()
                status_text.empty()
                st.rerun()
        elif existing_pdfs:
            st.info(f"{len(existing_pdfs)} PDF(s) already in the database. Use 'Rebuild Index' to reprocess.")

    # Rebuild Index button (full rebuild)
    st.divider()
    if st.button("🔨 Rebuild Index", help="Full rebuild: re-embed all elements from document store"):
        with st.spinner("Rebuilding index..."):
            try:
                build_index()
                st.success("Index rebuilt!")
                st.rerun()
            except Exception as e:
                st.error(f"Indexing failed: {e}")

    st.divider()

    # PDF Database + Summary Generation
    st.header("📚 PDFs")
    registry = load_registry()

    if not registry:
        st.info("No PDFs ingested yet. Upload PDFs above.")
    else:
        active_pdfs = []
        for pdf_name, info in registry.items():
            # PDF row: toggle + delete
            row_col1, row_col2 = st.columns([3, 1])
            with row_col1:
                is_active = st.checkbox(
                    f"{pdf_name}",
                    value=info.get("active", True),
                    key=f"pdf_toggle_{pdf_name}",
                )
                st.caption(f"{info.get('element_count', 0)} elements")
            with row_col2:
                if st.button("🗑️", key=f"del_{pdf_name}", help=f"Remove {pdf_name}"):
                    remove_pdf(pdf_name)
                    pdf_file = DATA_DIR / pdf_name
                    if pdf_file.exists():
                        pdf_file.unlink()
                    st.rerun()

            if is_active:
                active_pdfs.append(pdf_name)

            # Summary generation button
            has_summary = info.get("has_summary", False)
            if has_summary:
                if st.button("🔄 Regenerate Summary", key=f"regen_sum_{pdf_name}", use_container_width=True):
                    st.session_state[f"show_summary_form_{pdf_name}"] = True
            else:
                if st.button("📝 Generate Summary", key=f"gen_sum_{pdf_name}", use_container_width=True):
                    st.session_state[f"show_summary_form_{pdf_name}"] = True

            # Summary form (collapsible)
            if st.session_state.get(f"show_summary_form_{pdf_name}"):
                with st.container(border=True):
                    st.markdown(f"**Summary options for {pdf_name}**")

                    focus_overview = st.checkbox("Overview", value=True, key=f"focus_overview_{pdf_name}")
                    focus_topics = st.checkbox("Key Topics / TOC", value=True, key=f"focus_topics_{pdf_name}")
                    focus_components = st.checkbox("Components & Specs", value=True, key=f"focus_components_{pdf_name}")
                    focus_safety = st.checkbox("Safety & Warnings", value=True, key=f"focus_safety_{pdf_name}")

                    custom_instructions = st.text_area(
                        "Custom instructions (optional)",
                        placeholder="e.g., Focus on the cooling system and maintenance procedures",
                        key=f"custom_instr_{pdf_name}",
                        height=80,
                    )

                    gen_col1, gen_col2 = st.columns(2)
                    with gen_col1:
                        if st.button("Generate", key=f"do_gen_{pdf_name}", type="primary"):
                            focus_areas = []
                            if focus_overview:
                                focus_areas.append("overview")
                            if focus_topics:
                                focus_areas.append("topics")
                            if focus_components:
                                focus_areas.append("components")
                            if focus_safety:
                                focus_areas.append("safety")
                            if not focus_areas:
                                focus_areas = ["overview"]

                            with st.spinner("Generating summary..."):
                                try:
                                    generate_pdf_summary(
                                        pdf_name,
                                        focus_areas=focus_areas,
                                        custom_instructions=custom_instructions,
                                    )
                                    st.success("Summary generated!")
                                    st.session_state[f"show_summary_form_{pdf_name}"] = False
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Summary generation failed: {e}")
                    with gen_col2:
                        if st.button("Cancel", key=f"cancel_gen_{pdf_name}"):
                            st.session_state[f"show_summary_form_{pdf_name}"] = False
                            st.rerun()

            st.divider()

        # Update registry active states
        for pdf_name in registry:
            registry[pdf_name]["active"] = pdf_name in active_pdfs
        save_registry(registry)

    st.divider()

    # Transparency: show retrieved sources
    st.header("📋 Retrieved Sources")
    if "last_retrieved_items" in st.session_state and st.session_state.last_retrieved_items:
        for i, item in enumerate(st.session_state.last_retrieved_items):
            type_label = "📝 Text" if item["type"] == "text" else "🖼️ Image"
            source = item.get("source_pdf", "?")
            with st.expander(f"{type_label} — {source} p{item['page']} (score: {1 - item['distance']:.2%})"):
                if item["type"] == "text":
                    st.text(item["content"][:500] + ("..." if len(item["content"]) > 500 else ""))
                elif item["type"] == "image":
                    if item.get("path") and Path(item["path"]).exists():
                        st.image(item["path"], caption=f"{source} — Page {item['page']}")
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

# Get active PDFs for querying
registry = load_registry()
active_pdfs = [name for name, info in registry.items() if info.get("active", True)]

if not pipeline_ready:
    st.info("👆 Upload PDFs in the sidebar to get started.")
elif not active_pdfs:
    st.warning("No PDFs are active. Toggle at least one PDF in the sidebar to query.")
else:
    st.caption(f"Querying {len(active_pdfs)} active PDF(s): {', '.join(active_pdfs)}")

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
if prompt := st.chat_input("Ask a question about the manuals..."):
    if not pipeline_ready:
        st.error("Pipeline not ready. Ingest PDFs first.")
    elif not active_pdfs:
        st.error("No active PDFs. Toggle at least one in the sidebar.")
    else:
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Retrieve and stream answer
        with st.chat_message("assistant"):
            with st.spinner("Retrieving relevant context..."):
                retrieved_items, stream = retrieve_and_answer_stream(
                    prompt, active_pdfs=active_pdfs
                )

            # Store retrieved items for sidebar transparency
            st.session_state.last_retrieved_items = retrieved_items

            # Stream the answer
            full_response = st.write_stream(stream)

            # Show retrieved images inline
            image_paths = []
            for item in retrieved_items:
                if item["type"] == "image" and item.get("path") and Path(item["path"]).exists():
                    source = item.get("source_pdf", "?")
                    st.image(item["path"], caption=f"{source} — Page {item['page']}", width=400)
                    image_paths.append(item["path"])

        st.session_state.messages.append({
            "role": "assistant",
            "content": full_response,
            "images": image_paths,
        })
