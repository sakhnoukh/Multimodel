import json

import streamlit as st

from src.config import DATA_DIR, PDF_REGISTRY_PATH
from src.extract import remove_pdf
from src.summarize import (
    generate_pdf_summary,
    get_summary,
    delete_summary,
    list_summaries,
    chat_with_summary_stream,
)


def load_registry() -> dict:
    if PDF_REGISTRY_PATH.exists():
        return json.loads(PDF_REGISTRY_PATH.read_text())
    return {}


def save_registry(registry: dict) -> None:
    PDF_REGISTRY_PATH.write_text(json.dumps(registry, indent=2))


st.set_page_config(
    page_title="PDF Summaries",
    page_icon="📄",
    layout="wide",
)

st.title("📄 PDF Summaries")
st.markdown("Browse generated summaries and chat with them directly.")

registry = load_registry()

# --- Sidebar: PDF list + summary generation ---
with st.sidebar:
    st.header("📚 PDFs")

    if not registry:
        st.info("No PDFs ingested yet. Upload from the main page.")
    else:
        for pdf_name, info in registry.items():
            row_col1, row_col2 = st.columns([3, 1])
            with row_col1:
                st.write(f"**{pdf_name}**")
                st.caption(f"{info.get('element_count', 0)} elements")
            with row_col2:
                if st.button("🗑️", key=f"del_{pdf_name}", help=f"Remove {pdf_name}"):
                    remove_pdf(pdf_name)
                    pdf_file = DATA_DIR / pdf_name
                    if pdf_file.exists():
                        pdf_file.unlink()
                    st.rerun()

            has_summary = info.get("has_summary", False)
            if has_summary:
                if st.button("🔄 Regenerate Summary", key=f"regen_sum_{pdf_name}", use_container_width=True):
                    st.session_state[f"show_summary_form_{pdf_name}"] = True
            else:
                if st.button("📝 Generate Summary", key=f"gen_sum_{pdf_name}", use_container_width=True):
                    st.session_state[f"show_summary_form_{pdf_name}"] = True

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


# --- Main area: summary viewer + chat ---

summaries = list_summaries()

if not summaries:
    st.info("No summaries yet. Generate one from a PDF in the sidebar.")
else:
    # PDF selector
    selected_pdf = st.selectbox("Select a PDF summary to view:", summaries)

    if selected_pdf:
        summary_md = get_summary(selected_pdf)

        if summary_md:
            # Two columns: summary viewer | chat with summary
            col_viewer, col_chat = st.columns([1.2, 1], gap="medium")

            with col_viewer:
                st.subheader("📋 Summary")
                st.markdown(summary_md)

            with col_chat:
                st.subheader("💬 Chat with Summary")
                st.caption(f"Ask questions about {selected_pdf} based on its summary.")

                # Initialize chat history for this PDF
                chat_key = f"summary_chat_{selected_pdf}"
                if chat_key not in st.session_state:
                    st.session_state[chat_key] = []

                # Display chat history
                for message in st.session_state[chat_key]:
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])

                # Chat input
                if prompt := st.chat_input(f"Ask about {selected_pdf}..."):
                    # Display user message
                    with st.chat_message("user"):
                        st.markdown(prompt)
                    st.session_state[chat_key].append({"role": "user", "content": prompt})

                    # Build history for API (exclude current question)
                    history = st.session_state[chat_key][:-1]

                    # Stream answer
                    with st.chat_message("assistant"):
                        with st.spinner("Thinking..."):
                            stream = chat_with_summary_stream(
                                summary_text=summary_md,
                                question=prompt,
                                history=history,
                            )
                        full_response = st.write_stream(stream)

                    st.session_state[chat_key].append({
                        "role": "assistant",
                        "content": full_response,
                    })
        else:
            st.warning(f"Summary file for {selected_pdf} not found. Try regenerating it.")
