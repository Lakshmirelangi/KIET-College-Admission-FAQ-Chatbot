"""
KIET College Admission FAQ Chatbot
Main Streamlit application entry point.
"""

import streamlit as st
from backend.api_handler import get_bot_response_stream, validate_api_key
from backend.utils import (
    load_faq_data,
    get_all_categories,
    get_starter_questions,
    is_empty_or_whitespace,
    sanitize_input,
)

# ─────────────────────────── Page Config ─────────────────────────────
st.set_page_config(
    page_title="KIET Admissions Assistant",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────── Custom CSS ──────────────────────────────
st.markdown(
    """
    <style>
    /* ── Global ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* ── Hide default Streamlit chrome ── */
    #MainMenu, footer, header { visibility: hidden; }

    /* ── Top header bar ── */
    .kiet-header {
        background: linear-gradient(135deg, #1a237e 0%, #283593 60%, #3949ab 100%);
        padding: 1.2rem 2rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 1rem;
        box-shadow: 0 4px 20px rgba(26,35,126,0.3);
    }
    .kiet-header h1 {
        color: #ffffff;
        font-size: 1.5rem;
        font-weight: 700;
        margin: 0;
    }
    .kiet-header p {
        color: #c5cae9;
        font-size: 0.85rem;
        margin: 0.2rem 0 0 0;
    }
    .kiet-badge {
        background: #ffb300;
        color: #1a237e;
        font-size: 0.7rem;
        font-weight: 700;
        padding: 3px 10px;
        border-radius: 20px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* ── Chat message containers ── */
    .stChatMessage {
        border-radius: 12px !important;
        margin-bottom: 0.5rem;
        padding: 0.5rem !important;
    }

    /* ── Quick reply chips ── */
    .quick-chip-container {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 0.8rem 0;
    }

    /* ── Sidebar styling ── */
    .sidebar-section-title {
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #9e9e9e;
        margin: 1rem 0 0.4rem 0;
    }
    .category-pill {
        display: inline-block;
        background: #e8eaf6;
        color: #3f51b5;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.78rem;
        margin: 2px;
    }

    /* ── Status indicator ── */
    .status-dot-green {
        height: 10px; width: 10px;
        background: #4caf50;
        border-radius: 50%;
        display: inline-block;
        margin-right: 6px;
    }
    .status-dot-red {
        height: 10px; width: 10px;
        background: #f44336;
        border-radius: 50%;
        display: inline-block;
        margin-right: 6px;
    }

    /* ── Disclaimer box ── */
    .disclaimer-box {
        background: #fff8e1;
        border-left: 4px solid #ffb300;
        padding: 0.6rem 1rem;
        border-radius: 0 8px 8px 0;
        font-size: 0.8rem;
        color: #5d4037;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────── Session State Init ───────────────────────
def init_session_state():
    defaults = {
        "conversation_history": [],
        "faq_data": None,
        "api_status": None,
        "greeted": False,
        "pending_quick_reply": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()

# ─────────────────────────── Load FAQ Data ───────────────────────────
@st.cache_data(show_spinner=False)
def cached_load_faq():
    return load_faq_data()


try:
    if st.session_state.faq_data is None:
        st.session_state.faq_data = cached_load_faq()
except FileNotFoundError as e:
    st.error(f"❌ FAQ data file not found: {e}")
    st.stop()

faq_data = st.session_state.faq_data

# ─────────────────────────── Sidebar ─────────────────────────────────
with st.sidebar:
    st.markdown("## 🎓 KIET Admissions Bot")
    st.markdown("---")

    # API Status
    st.markdown('<p class="sidebar-section-title">🔌 API Status</p>', unsafe_allow_html=True)
    if st.button("🔍 Check API Connection", use_container_width=True):
        with st.spinner("Checking..."):
            is_valid, msg = validate_api_key()
            st.session_state.api_status = (is_valid, msg)

    if st.session_state.api_status:
        is_valid, msg = st.session_state.api_status
        if is_valid:
            st.markdown(
                '<span class="status-dot-green"></span>Connected', unsafe_allow_html=True
            )
        else:
            st.markdown(
                f'<span class="status-dot-red"></span>{msg}', unsafe_allow_html=True
            )

    st.markdown("---")

    # FAQ Categories browser
    st.markdown('<p class="sidebar-section-title">📂 Browse by Topic</p>', unsafe_allow_html=True)
    categories = get_all_categories(faq_data)
    selected_category = st.selectbox(
        "Select a category",
        ["All Topics"] + categories,
        label_visibility="collapsed",
    )

    if selected_category != "All Topics":
        cat_questions = []
        for cat in faq_data["faq_categories"]:
            if cat["category"] == selected_category:
                cat_questions = [q["question"] for q in cat["questions"]]
                break

        for q in cat_questions[:6]:
            if st.button(f"💬 {q[:55]}...", key=f"cat_{q[:20]}", use_container_width=True):
                st.session_state.pending_quick_reply = q

    st.markdown("---")

    # Institution info
    st.markdown('<p class="sidebar-section-title">🏫 Institution</p>', unsafe_allow_html=True)
    st.markdown(
        f"""
        **{faq_data['institution']}**  
        📍 Kakinada, Andhra Pradesh  
        🌐 [kiet.edu.in]({faq_data['contact']['website']})  
        📧 {faq_data['contact']['email']}
        """
    )

    st.markdown("---")

    # Clear chat
    if st.button("🗑️ Clear Conversation", use_container_width=True, type="secondary"):
        st.session_state.conversation_history = []
        st.session_state.greeted = False
        st.rerun()

    # Stats
    st.markdown('<p class="sidebar-section-title">📊 Knowledge Base</p>', unsafe_allow_html=True)
    total_q = sum(len(c["questions"]) for c in faq_data["faq_categories"])
    total_cats = len(faq_data["faq_categories"])
    st.markdown(f"- **{total_q}** questions indexed")
    st.markdown(f"- **{total_cats}** topic categories")

# ─────────────────────────── Main Chat Area ──────────────────────────
# Header
st.markdown(
    """
    <div class="kiet-header">
        <div style="font-size:2.5rem;">🎓</div>
        <div>
            <h1>KIET Admissions Assistant</h1>
            <p>Your official guide for admissions at Kakinada Institute of Engineering &amp; Technology</p>
        </div>
        <div style="margin-left:auto;">
            <span class="kiet-badge">AI Powered</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Disclaimer
st.markdown(
    """
    <div class="disclaimer-box">
        ⚠️ <strong>Note:</strong> This chatbot answers from our official FAQ database.
        For the most current fee figures, dates, and seat availability, always verify with the
        <strong>KIET Admissions Office</strong>.
    </div>
    """,
    unsafe_allow_html=True,
)

# Render conversation history
for msg in st.session_state.conversation_history:
    with st.chat_message(msg["role"], avatar="🧑‍🎓" if msg["role"] == "user" else "🎓"):
        st.markdown(msg["content"])

# ─── Welcome message on fresh load ───
if not st.session_state.conversation_history and not st.session_state.greeted:
    with st.chat_message("assistant", avatar="🎓"):
        welcome = (
            "👋 **Welcome to the KIET Admissions Assistant!**\n\n"
            "I can help you with:\n"
            "- 🎓 Admission process & eligibility\n"
            "- 💰 Fee structure & scholarships\n"
            "- 🏠 Hostel & transport facilities\n"
            "- 📊 Placement records\n"
            "- 📄 Required documents\n\n"
            "Ask me anything about admissions at **Kakinada Institute of Engineering & Technology**!"
        )
        st.markdown(welcome)
    st.session_state.greeted = True

# ─── Starter quick-reply chips (shown only at start) ───
if len(st.session_state.conversation_history) == 0:
    st.markdown("**🚀 Popular Questions — click to ask:**")
    starter_questions = get_starter_questions(faq_data)
    cols = st.columns(4)
    for i, q in enumerate(starter_questions):
        col = cols[i % 4]
        with col:
            if st.button(q, key=f"starter_{i}", use_container_width=True):
                st.session_state.pending_quick_reply = q
                st.rerun()

# ─── Handle pending quick reply (from sidebar or chips) ───
if st.session_state.pending_quick_reply:
    user_input = st.session_state.pending_quick_reply
    st.session_state.pending_quick_reply = None
    st.session_state.conversation_history.append(
        {"role": "user", "content": user_input}
    )
    with st.chat_message("user", avatar="🧑‍🎓"):
        st.markdown(user_input)

    with st.chat_message("assistant", avatar="🎓"):
        response_placeholder = st.empty()
        full_response = ""
        with st.spinner(""):
            try:
                for chunk in get_bot_response_stream(
                    user_input,
                    st.session_state.conversation_history[:-1],  # exclude just-added user msg
                    faq_data,
                ):
                    full_response += chunk
                    response_placeholder.markdown(full_response + "▌")
                response_placeholder.markdown(full_response)
            except Exception as e:
                full_response = (
                    f"⚠️ I encountered an error: `{str(e)}`\n\n"
                    "Please check your API key in `.env` and try again."
                )
                response_placeholder.markdown(full_response)

    st.session_state.conversation_history.append(
        {"role": "assistant", "content": full_response}
    )
    st.rerun()

# ─── Main chat input ───
user_input = st.chat_input("Ask about admissions, fees, hostel, placements...")

if user_input:
    if is_empty_or_whitespace(user_input):
        st.warning("Please type a question.")
    else:
        user_input = sanitize_input(user_input)

        # Display user message
        with st.chat_message("user", avatar="🧑‍🎓"):
            st.markdown(user_input)

        # Stream assistant response
        with st.chat_message("assistant", avatar="🎓"):
            response_placeholder = st.empty()
            full_response = ""
            try:
                for chunk in get_bot_response_stream(
                    user_input,
                    st.session_state.conversation_history,
                    faq_data,
                ):
                    full_response += chunk
                    response_placeholder.markdown(full_response + "▌")
                response_placeholder.markdown(full_response)
            except EnvironmentError as e:
                full_response = (
                    f"⚠️ **API Key Missing**\n\n{str(e)}\n\n"
                    "**Steps to fix:**\n"
                    "1. Create a `.env` file in the project root\n"
                    "2. Add: `ANTHROPIC_API_KEY=your_key_here`\n"
                    "3. Restart the app with `streamlit run app.py`"
                )
                response_placeholder.markdown(full_response)
            except Exception as e:
                full_response = (
                    f"⚠️ Something went wrong: `{str(e)}`\n\n"
                    "Please try again or contact the admissions office at "
                    f"{faq_data['contact']['email']}"
                )
                response_placeholder.markdown(full_response)

        # Update conversation history
        st.session_state.conversation_history.append(
            {"role": "user", "content": user_input}
        )
        st.session_state.conversation_history.append(
            {"role": "assistant", "content": full_response}
        )