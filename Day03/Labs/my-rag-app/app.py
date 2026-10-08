"""
AskIT Marcin - A RAG app to chat with PDFs.
Upload. Ask. Done.
"""

import builtins
import sys
from pathlib import Path


def safe_text(value):
    return builtins.str(value)


# Add repo root to path to import askit_core
sys.path.insert(0, safe_text(Path(__file__).resolve().parents[3]))

import streamlit as st
import numpy as np
from pypdf import PdfReader
from askit_core import bedrock, config

# ============================================================================
# SETUP: Page config, CSS theming, session state initialization
# ============================================================================

st.set_page_config(page_title="AskIT Marcin", page_icon="🤖", layout="wide")

# Purple on black theme with CSS
st.markdown("""
<style>
    :root {
        --primary: #B366FF;
        --dark: #0a0e27;
    }
    body { background-color: var(--dark); color: #e0e0e0; }
    .stChatMessage { border-radius: 10px; }
    .stButton > button {
        background: linear-gradient(135deg, var(--primary) 0%, #8B45D9 100%);
        color: white; border: none; border-radius: 8px; font-weight: bold;
    }
    .stButton > button:hover { transform: scale(1.02); }
    header { color: var(--primary); font-weight: bold; }
    .source-badge { 
        background: var(--primary); color: black; 
        padding: 2px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state for PDF data and chat
if "chunks" not in st.session_state:
    st.session_state.chunks = []
    st.session_state.embeddings = []
    st.session_state.pdf_name = None
    st.session_state.messages = []
    st.session_state.pages_count = 0
    st.session_state.chunks_count = 0

# ============================================================================
# HELPER FUNCTIONS: Chunking, embedding, cosine similarity
# ============================================================================

def chunk_text(text: str, chunk_size: int = 120, overlap: int = 30) -> list[str]:
    """
    Split text into chunks by words. WHY: Simple, readable chunking strategy.
    chunk_size: words per chunk. overlap: words to repeat at chunk boundaries.
    """
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


def embed_text(text: str, client) -> list[float]:
    """
    Call AWS Titan Embeddings v2. WHY: Convert text to vector for similarity search.
    Returns: 512-dim vector or None if API fails.
    """
    try:
        response = client.invoke_model(
            modelId="amazon.titan-embed-text-v2:0",
            body=__import__("json").dumps({
                "inputText": text,
                "dimensions": 512,
                "normalize": True
            })
        )
        return __import__("json").loads(
            response["body"].read()
        )["embedding"]
    except Exception as e:
        st.error(f"❌ Embedding failed. Check: .env keys, AWS region, Titan model access. Error: {safe_text(e)[:100]}")
        return None


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors. WHY: Measure relevance of chunks.
    """
    a, b = np.array(vec_a), np.array(vec_b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9)


def find_top_chunks(question_embedding: list[float], top_k: int) -> list[tuple]:
    """
    Find top-K most similar chunks. WHY: Retrieve relevant context for the question.
    Returns: [(chunk_text, page_num, similarity_score), ...]
    """
    if not st.session_state.embeddings:
        return []
    scores = [cosine_similarity(question_embedding, emb) for emb in st.session_state.embeddings]
    top_indices = np.argsort(scores)[-top_k:][::-1]
    return [
        (st.session_state.chunks[i]["text"], st.session_state.chunks[i]["page"], scores[i])
        for i in top_indices
    ]

# ============================================================================
# MAIN: Header and sidebar controls
# ============================================================================

st.markdown("<h1 style='color: #B366FF;'>🤖 AskIT Marcin</h1>", unsafe_allow_html=True)
st.markdown("<p style='color: #8B45D9; font-style: italic;'>Upload. Ask. Done.</p>", unsafe_allow_html=True)

# Sidebar configuration
with st.sidebar:
    st.markdown("<h3 style='color: #B366FF;'>⚙️ Settings</h3>", unsafe_allow_html=True)
    
    top_k = st.slider("Top-K chunks to retrieve", min_value=1, max_value=6, value=3)
    chunk_size = st.slider("Chunk size (words)", min_value=50, max_value=200, value=120)
    overlap = st.slider("Chunk overlap (words)", min_value=0, max_value=50, value=30)
    
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.markdown("---")
    st.markdown("""
    <div style='background: #1a1f3a; padding: 12px; border-radius: 8px; border-left: 3px solid #B366FF;'>
        <b>📋 About Marcin</b><br>
        Team: DevPro Academy<br>
        Date: 2026-10-07<br>
        <i>Calm senior engineer with dad jokes.</i>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown(
        "<p style='text-align: center; font-size: 0.8em; color: #666;'>Built by Marcin with vibe coding at DevPro Academy</p>",
        unsafe_allow_html=True
    )

# ============================================================================
# PDF UPLOAD & INDEX BUILDING
# ============================================================================

uploaded_file = st.file_uploader("📤 Upload your PDF", type="pdf")

if uploaded_file:
    # Clear old data if new PDF uploaded
    if st.session_state.pdf_name != uploaded_file.name:
        st.session_state.chunks = []
        st.session_state.embeddings = []
        st.session_state.messages = []
        st.session_state.pdf_name = uploaded_file.name
    
    if st.button("🔨 Build Index", use_container_width=True):
        try:
            # Step 1: Read PDF and extract text with page numbers
            reader = PdfReader(uploaded_file)
            st.session_state.pages_count = len(reader.pages)
            
            all_text_with_pages = []
            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                if text.strip():
                    all_text_with_pages.append((text, page_num))
            
            if not all_text_with_pages:
                st.warning("📄 This PDF appears to be scanned (no text found). Please upload a text-based PDF.")
                st.stop()
            
            # Step 2: Chunk the text
            st.session_state.chunks = []
            for text, page_num in all_text_with_pages:
                for chunk in chunk_text(text, chunk_size, overlap):
                    st.session_state.chunks.append({
                        "text": chunk,
                        "page": page_num
                    })
            
            st.session_state.chunks_count = len(st.session_state.chunks)
            
            # Step 3: Embed chunks (max 4 at a time)
            client = bedrock.client()
            st.session_state.embeddings = []
            progress_bar = st.progress(0)
            
            for i in range(0, len(st.session_state.chunks), 4):
                batch = st.session_state.chunks[i : i + 4]
                for chunk in batch:
                    emb = embed_text(chunk["text"], client)
                    if emb is None:
                        st.stop()
                    st.session_state.embeddings.append(emb)
                
                progress_bar.progress(min((i + 4) / len(st.session_state.chunks), 1.0))
            
            st.success(
                f"✅ Index built! {st.session_state.pages_count} pages, "
                f"{st.session_state.chunks_count} chunks ready."
            )
        
        except Exception as e:
            st.error(f"❌ Failed to build index. Error: {safe_text(e)[:150]}")

# ============================================================================
# CHAT INTERFACE
# ============================================================================

if st.session_state.chunks and st.session_state.embeddings:
    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🤖" if msg["role"] == "assistant" else "👤"):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and "sources" in msg:
                with st.expander("📚 Sources"):
                    for src in msg["sources"]:
                        st.markdown(
                            f"<span class='source-badge'>p.{src['page']}</span> "
                            f"Relevance: {src['score']:.2f}",
                            unsafe_allow_html=True
                        )
                        st.caption(src["text"][:200] + "...")
    
    # Chat input
    if prompt := st.chat_input("Ask about your PDF..."):
        # Show user message
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Process: embed question, find top chunks, call LLM
        client = bedrock.client()
        question_emb = embed_text(prompt, client)
        
        if question_emb:
            top_chunks = find_top_chunks(question_emb, top_k)
            
            # Build context from top chunks
            context = "\n\n".join([f"[p.{c[1]}] {c[0]}" for c in top_chunks])
            
            # Build prompt with personality
            system_prompt = (
                "You are a calm senior engineer. Be formal and sometimes end with a joke. "
                "Answer ONLY from the provided context. If the answer is not in the context, "
                "say you could not find it in the PDF. Always cite pages like [p.3]."
            )
            
            full_prompt = f"{system_prompt}\n\nContext:\n{context}\n\nQuestion: {prompt}"
            
            # Call chat model
            try:
                response = client.converse(
                    modelId=config.SMALL_MODEL,
                    messages=[{
                        "role": "user",
                        "content": [{"text": full_prompt}]
                    }],
                    inferenceConfig={"maxTokens": 500, "temperature": 0.2}
                )
                answer = response["output"]["message"]["content"][0]["text"]
                
                # Show assistant message with sources
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(answer)
                    
                    with st.expander("📚 Sources"):
                        for chunk_text, page_num, similarity in top_chunks:
                            st.markdown(
                                f"<span class='source-badge'>p.{page_num}</span> "
                                f"Relevance: {similarity:.2f}",
                                unsafe_allow_html=True
                            )
                            st.caption(chunk_text[:200] + "...")
                
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "sources": [
                        {"page": c[1], "score": c[2], "text": c[0]}
                        for c in top_chunks
                    ]
                })
            
            except Exception as e:
                st.error(f"❌ Chat failed. Check: .env keys, AWS region, Nova Micro model access. Error: {safe_text(e)[:100]}")
else:
    if uploaded_file:
        st.info("👆 Click 'Build Index' to get started!")
