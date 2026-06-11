"""
KIET College Admission FAQ Chatbot
Main Streamlit application entry point with premium UI styling.
Features: Feedback rating, typing indicator, "Did you mean?" suggestions,
          persona-based personalization, PDF export, unanswered questions log.
"""

import streamlit as st
import base64
import uuid
import json
import csv
import os
import re
from datetime import datetime
from io import BytesIO
from backend.api_handler import get_bot_response_stream
from backend.utils import (
    load_faq_data,
    get_all_categories,
    get_starter_questions,
    is_empty_or_whitespace,
    sanitize_input,
)

# ─────────────────────────── Helper Utilities ────────────────────────

def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        return ""

logo_base64 = get_base64_image("logo.png")

# ── Feedback Storage ──────────────────────────────────────────────────
FEEDBACK_FILE = "feedback_log.csv"

def save_feedback(question: str, answer: str, rating: str):
    file_exists = os.path.isfile(FEEDBACK_FILE)
    with open(FEEDBACK_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "rating", "question", "answer"])
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "timestamp": datetime.now().isoformat(),
            "rating": rating,
            "question": question[:300],
            "answer": answer[:500],
        })

# ── Unanswered Questions Log ──────────────────────────────────────────
UNANSWERED_FILE = "unanswered_questions.json"

LOW_CONFIDENCE_PHRASES = [
    "i don't have", "i'm not sure", "i cannot find", "no information",
    "not available", "i don't know", "unable to answer", "i couldn't find",
    "outside my knowledge", "please contact", "verify with",
]

def is_low_confidence(response: str) -> bool:
    lower = response.lower()
    return any(phrase in lower for phrase in LOW_CONFIDENCE_PHRASES)

def log_unanswered_question(question: str, response: str):
    records = []
    if os.path.isfile(UNANSWERED_FILE):
        try:
            with open(UNANSWERED_FILE, "r", encoding="utf-8") as f:
                records = json.load(f)
        except Exception:
            records = []
    records.append({
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "bot_response_snippet": response[:300],
    })
    with open(UNANSWERED_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

# ── "Did you mean?" suggestion matcher ───────────────────────────────
def get_related_questions(user_input: str, faq_data: dict, top_n: int = 3) -> list:
    """Simple keyword overlap scoring to find related FAQ questions."""
    words = set(re.sub(r"[^\w\s]", "", user_input.lower()).split()) - {
        "what", "is", "are", "how", "the", "a", "an", "for", "in",
        "of", "to", "do", "can", "i", "my", "at", "about",
    }
    if not words:
        return []
    scored = []
    for cat in faq_data.get("faq_categories", []):
        for item in cat.get("questions", []):
            q = item["question"]
            q_words = set(re.sub(r"[^\w\s]", "", q.lower()).split())
            score = len(words & q_words)
            if score > 0:
                scored.append((score, q))
    scored.sort(key=lambda x: -x[0])
    return [q for _, q in scored[:top_n]]

# ── PDF Export ────────────────────────────────────────────────────────
def generate_chat_pdf(history: list, session_title: str) -> bytes:
    """Generate a clean PDF from chat history using reportlab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "Title", parent=styles["Heading1"],
            fontSize=16, textColor=colors.HexColor("#1a237e"),
            spaceAfter=4,
        )
        meta_style = ParagraphStyle(
            "Meta", parent=styles["Normal"],
            fontSize=9, textColor=colors.grey, spaceAfter=12,
        )
        user_style = ParagraphStyle(
            "User", parent=styles["Normal"],
            fontSize=10, textColor=colors.HexColor("#0d47a1"),
            leftIndent=0, spaceAfter=4, leading=14,
            fontName="Helvetica-Bold",
        )
        bot_style = ParagraphStyle(
            "Bot", parent=styles["Normal"],
            fontSize=10, textColor=colors.HexColor("#212121"),
            leftIndent=12, spaceAfter=14, leading=15,
        )

        story = []
        story.append(Paragraph("KIET Admissions Assistant — Chat Export", title_style))
        story.append(Paragraph(
            f"Session: {session_title} &nbsp;|&nbsp; Exported: {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
            meta_style,
        ))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e0e0e0"), spaceAfter=14))

        for msg in history:
            if msg["role"] == "user":
                clean_q = msg["content"].split(" [Context constraint:")[0]
                story.append(Paragraph(f"🧑 You: {clean_q}", user_style))
            else:
                # Strip markdown bold/italic for PDF
                clean_ans = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", msg["content"])
                clean_ans = clean_ans.replace("\n", "<br/>")
                story.append(Paragraph(f"🎓 Assistant: {clean_ans}", bot_style))

        story.append(Spacer(1, 20))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e0e0e0")))
        story.append(Paragraph(
            "This export is for reference only. Verify details with the KIET Admissions Office.",
            meta_style,
        ))

        doc.build(story)
        return buffer.getvalue()

    except ImportError:
        # Fallback: plain text
        lines = [f"KIET Admissions Chat Export — {session_title}\n", "=" * 60 + "\n"]
        for msg in history:
            prefix = "You" if msg["role"] == "user" else "Assistant"
            clean = msg["content"].split(" [Context constraint:")[0]
            lines.append(f"{prefix}:\n{clean}\n\n")
        return "\n".join(lines).encode("utf-8")

# ── Persona-based starter config ─────────────────────────────────────
PERSONA_CONFIG = {
    "🎓 New Applicant": {
        "greeting": "Welcome! I'll help you navigate the KIET admissions process step-by-step.",
        "starters": [
            "What are the eligibility criteria for B.TECH?",
            "When does counseling registration open?",
            "What documents do I need for admission?",
            "What is the fee structure for B.TECH?",
        ],
    },
    "📚 Existing Student": {
        "greeting": "Hello! I can help with academic, hostel, or campus-related queries.",
        "starters": [
            "What facilities are available in the hostel?",
            "How do I apply for a scholarship?",
            "What are the placement statistics?",
            "What extracurricular activities are available?",
        ],
    },
    "👨‍👩‍👧 Parent / Guardian": {
        "greeting": "Welcome! I'm here to answer all your questions about KIET for your ward.",
        "starters": [
            "Is the campus safe and secure?",
            "What are the hostel fees and facilities?",
            "What is the placement record of KIET?",
            "How can I contact the admissions office?",
        ],
    },
}

# ─────────────────────────── Page Config ─────────────────────────────
st.set_page_config(
    page_title="KIET Admissions Assistant",
    page_icon="logo.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────── Custom CSS ──────────────────────────────
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif;
    }}
    .stApp {{
        background-color: #0e0e10;
    }}
    #MainMenu, footer, header {{ visibility: hidden; }}

    /* ── Header ── */
    .kiet-header {{
        background: linear-gradient(135deg, #121843 0%, #1a237e 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 1.2rem;
        border: 1px solid rgba(255,255,255,0.05);
        box-shadow: 0 4px 24px rgba(0,0,0,0.2);
        animation: headerSlideIn 0.5s ease forwards;
        position: relative;
        overflow: hidden;
    }}
    .kiet-header::after {{
        content: '';
        position: absolute;
        top: -50%; left: -60%;
        width: 40%; height: 200%;
        background: linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.06) 50%, transparent 60%);
        animation: shimmer 3.5s infinite;
    }}
    @keyframes shimmer {{
        0%   {{ left: -60%; }}
        100% {{ left: 130%; }}
    }}
    @keyframes headerSlideIn {{
        from {{ opacity: 0; transform: translateY(-16px); }}
        to   {{ opacity: 1; transform: translateY(0); }}
    }}
    .kiet-logo {{
        width: 55px; height: 55px;
        object-fit: contain;
        border-radius: 8px;
        background: white;
        padding: 5px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }}
    .sidebar-logo {{
        width: 28px; height: 28px;
        object-fit: contain;
        border-radius: 4px;
        background: white;
        padding: 2px;
        vertical-align: middle;
        margin-right: 8px;
        display: inline-block;
    }}
    .kiet-header h1 {{
        color: #ffffff; font-size: 1.6rem; font-weight: 700;
        margin: 0; letter-spacing: -0.02em;
    }}
    .kiet-header p {{
        color: #9fa8da; font-size: 0.9rem;
        margin: 0.2rem 0 0 0; opacity: 0.9;
    }}
    /* ── Buttons ── */
    div.stButton > button {{
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        border-radius: 8px !important;
    }}
    div.stButton > button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(26,35,126,0.35) !important;
    }}
    div.stButton > button:active {{
        transform: translateY(0px) scale(0.97);
    }}

    /* ── Chat messages fade + slide in ── */
    .stChatMessage {{
        border-radius: 12px !important;
        margin-bottom: 0.6rem;
        padding: 0.8rem !important;
        border: 1px solid rgba(255,255,255,0.02);
        animation: msgFadeIn 0.35s ease forwards;
    }}
    @keyframes msgFadeIn {{
        from {{ opacity: 0; transform: translateY(10px); }}
        to   {{ opacity: 1; transform: translateY(0); }}
    }}

    /* ── Sidebar ── */
    .sidebar-section-title {{
        font-size: 0.72rem; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.1em;
        color: #757575; margin: 1.4rem 0 0.5rem 0;
    }}
    div[data-baseweb="select"] {{
        border: 1px solid rgba(255,255,255,0.07) !important;
        border-radius: 8px !important;
    }}

    /* ── Status dot ── */
    .status-container {{
        display: flex; align-items: center; gap: 8px;
        font-size: 0.8rem; color: #a0a0a5;
        margin-top: -5px; margin-bottom: 10px;
    }}
    .pulse-dot {{
        width: 8px; height: 8px;
        background-color: #23a55a; border-radius: 50%;
        box-shadow: 0 0 0 0 rgba(35,165,90,0.7);
        animation: pulse 1.6s infinite;
    }}
    @keyframes pulse {{
        0%   {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(35,165,90,0.8); }}
        70%  {{ transform: scale(1.1); box-shadow: 0 0 0 8px rgba(35,165,90,0); }}
        100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(35,165,90,0); }}
    }}

    /* ── Typing indicator ── */
    .typing-indicator {{
        display: flex; align-items: center; gap: 6px;
        padding: 10px 14px;
        color: #9fa8da; font-size: 0.85rem;
    }}
    .typing-dot {{
        width: 7px; height: 7px;
        background: #7986cb; border-radius: 50%;
        animation: bounce 1.2s infinite ease-in-out;
    }}
    .typing-dot:nth-child(2) {{ animation-delay: 0.2s; }}
    .typing-dot:nth-child(3) {{ animation-delay: 0.4s; }}
    @keyframes bounce {{
        0%, 80%, 100% {{ transform: translateY(0); opacity: 0.5; }}
        40%            {{ transform: translateY(-6px); opacity: 1; }}
    }}

    /* ── Feedback buttons ── */
    .feedback-row {{
        display: flex; align-items: center; gap: 8px;
        margin-top: 8px; margin-bottom: 2px;
        font-size: 0.78rem; color: #757575;
    }}
    .feedback-btn {{
        cursor: pointer;
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 6px; padding: 3px 10px;
        font-size: 0.82rem;
        transition: background 0.2s;
    }}
    .feedback-btn:hover {{ background: rgba(255,255,255,0.1); }}

    /* ── "Did you mean?" chips ── */
    .dym-container {{
        background: rgba(121,134,203,0.06);
        border: 1px solid rgba(121,134,203,0.15);
        border-radius: 8px;
        padding: 10px 14px;
        margin-top: 8px;
        font-size: 0.82rem;
        animation: msgFadeIn 0.3s ease forwards;
    }}
    .dym-title {{ color: #9fa8da; margin-bottom: 6px; font-weight: 600; }}

    /* ── Badge pulse ── */
    .kiet-badge {{
        background: rgba(255,179,0,0.15);
        color: #ffb300;
        border: 1px solid rgba(255,179,0,0.3);
        font-size: 0.7rem; font-weight: 600;
        padding: 4px 12px; border-radius: 20px;
        text-transform: uppercase; letter-spacing: 0.06em;
        animation: badgePulse 2.5s ease-in-out infinite;
    }}
    @keyframes badgePulse {{
        0%, 100% {{ box-shadow: 0 0 0 0 rgba(255,179,0,0.0); }}
        50%       {{ box-shadow: 0 0 0 6px rgba(255,179,0,0.15); }}
    }}

    /* ── Disclaimer slide in ── */
    .disclaimer-box {{
        background: rgba(255,179,0,0.03);
        border-left: 3px solid #ffb300;
        padding: 0.8rem 1.2rem; border-radius: 6px;
        font-size: 0.85rem; color: #ffe082;
        margin-bottom: 1.5rem;
        border-top: 1px solid rgba(255,179,0,0.04);
        border-right: 1px solid rgba(255,179,0,0.04);
        border-bottom: 1px solid rgba(255,179,0,0.04);
        animation: msgFadeIn 0.5s ease forwards;
    }}

    /* ── Persona selector ── */
    .persona-card {{
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 10px;
        padding: 1.1rem 1.3rem;
        text-align: center;
        cursor: pointer;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        animation: cardPopIn 0.4s ease forwards;
    }}
    .persona-card:hover {{
        background: rgba(26,35,126,0.25);
        border-color: rgba(121,134,203,0.5);
        transform: translateY(-4px) scale(1.02);
        box-shadow: 0 10px 30px rgba(26,35,126,0.3);
    }}
    .persona-emoji {{ font-size: 2rem; margin-bottom: 6px; }}
    .persona-label {{ color: #fff; font-size: 0.88rem; font-weight: 600; }}
    .persona-sub {{ color: #757575; font-size: 0.75rem; margin-top: 2px; }}

    /* ── Info/sidebar boxes ── */
    .sidebar-info-box {{
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.05);
        border-radius: 8px;
        padding: 10px 12px;
        font-size: 0.8rem; line-height: 1.4;
    }}

    /* ── Metric cards ── */
    .metric-container {{
        background: linear-gradient(135deg,rgba(255,255,255,0.03) 0%,rgba(255,255,255,0.01) 100%);
        border: 1px solid rgba(255,255,255,0.06);
        padding: 1.2rem; border-radius: 10px; text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        animation: cardPopIn 0.4s ease forwards;
    }}
    .metric-container:hover {{
        border-color: rgba(121,134,203,0.5);
        transform: translateY(-4px);
        box-shadow: 0 12px 32px rgba(26,35,126,0.3);
    }}
    @keyframes cardPopIn {{
        from {{ opacity: 0; transform: scale(0.94) translateY(8px); }}
        to   {{ opacity: 1; transform: scale(1) translateY(0); }}
    }}
    .metric-val {{
        font-size: 1.7rem; font-weight: 700;
        background: linear-gradient(90deg,#ffffff,#9fa8da);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 2px;
    }}
    .metric-lbl {{
        font-size: 0.75rem; color: #7e7e86;
        text-transform: uppercase; letter-spacing: 0.06em;
    }}

    /* ── Feature cards ── */
    .feature-card {{
        background: rgba(255,255,255,0.01);
        border: 1px solid rgba(255,255,255,0.04);
        border-radius: 8px; padding: 1rem 1.2rem; height: 100%;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        animation: cardPopIn 0.45s ease forwards;
    }}
    .feature-card:hover {{
        background: rgba(26,35,126,0.12);
        border-color: rgba(121,134,203,0.35);
        transform: translateY(-3px);
        box-shadow: 0 8px 24px rgba(26,35,126,0.2);
    }}
    .feature-title {{
        color: #ffffff; font-size: 0.92rem; font-weight: 600;
        margin-bottom: 4px; display: flex; align-items: center; gap: 8px;
    }}
    .feature-desc {{ color: #8a8a93; font-size: 0.82rem; line-height: 1.4; }}

    /* ── Helpdesk banner ── */
    .helpdesk-banner {{
        background: linear-gradient(90deg,rgba(18,24,67,0.3) 0%,rgba(26,35,126,0.1) 100%);
        border: 1px solid rgba(26,35,126,0.25);
        padding: 1rem 1.5rem; border-radius: 8px; margin-top: 2.5rem;
        display: flex; justify-content: space-between; align-items: center;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────── Session State Init ───────────────────────
def init_session_state():
    if "chat_sessions" not in st.session_state:
        st.session_state["chat_sessions"] = {}
    if "current_session_id" not in st.session_state:
        first_id = str(uuid.uuid4())
        st.session_state["chat_sessions"][first_id] = {
            "title": "New Chat Session",
            "history": [],
            "greeted": False,
        }
        st.session_state["current_session_id"] = first_id

    defaults = {
        "faq_data": None,
        "pending_quick_reply": None,
        "feedback_given": {},      # {msg_index: "up"/"down"}
        "persona": None,           # selected persona string
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

curr_id = st.session_state["current_session_id"]
active_session = st.session_state["chat_sessions"].get(curr_id)

if active_session is None:
    session_keys = list(st.session_state["chat_sessions"].keys())
    if session_keys:
        st.session_state["current_session_id"] = session_keys[0]
        curr_id = session_keys[0]
        active_session = st.session_state["chat_sessions"][curr_id]
    else:
        first_id = str(uuid.uuid4())
        st.session_state["chat_sessions"][first_id] = {
            "title": "New Chat Session",
            "history": [],
            "greeted": False,
        }
        st.session_state["current_session_id"] = first_id
        curr_id = first_id
        active_session = st.session_state["chat_sessions"][curr_id]

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
    if logo_base64:
        st.markdown(
            f'## <img src="data:image/png;base64,{logo_base64}" class="sidebar-logo">'
            '<span style="vertical-align:middle;">KIET Admissions</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown("## 🎓 KIET Admissions")

    st.markdown(
        """
        <div class="status-container">
            <div class="pulse-dot"></div>
            <span>AI Assistant Online</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ── PDF Export Button ──
    if active_session["history"]:
        st.markdown('<p class="sidebar-section-title">📥 Export</p>', unsafe_allow_html=True)
        if st.button("⬇️ Download Chat as PDF", use_container_width=True):
            pdf_bytes = generate_chat_pdf(active_session["history"], active_session["title"])
            st.download_button(
                label="📄 Click to Save PDF",
                data=pdf_bytes,
                file_name=f"KIET_Chat_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        st.markdown("---")

    if st.button("➕ New Chat", use_container_width=True, type="secondary"):
        new_id = str(uuid.uuid4())
        st.session_state["chat_sessions"][new_id] = {
            "title": "New Chat Session",
            "history": [],
            "greeted": False,
        }
        st.session_state["current_session_id"] = new_id
        st.session_state["persona"] = None
        st.rerun()

    st.markdown('<p class="sidebar-section-title">🕒 Recent Conversations</p>', unsafe_allow_html=True)

    for session_id, session_info in list(st.session_state["chat_sessions"].items()):
        display_title = session_info["title"]
        if len(display_title) > 20:
            display_title = display_title[:18] + "..."
        button_label = display_title if display_title == "New Chat Session" else f"💬 {display_title}"

        hist_col, del_col = st.columns([0.82, 0.18])
        with hist_col:
            if st.button(button_label, key=f"session_{session_id}", use_container_width=True):
                st.session_state["current_session_id"] = session_id
                st.rerun()
        with del_col:
            if st.button("✕", key=f"delete_{session_id}", use_container_width=True, help="Delete this chat"):
                del st.session_state["chat_sessions"][session_id]
                st.rerun()

    st.markdown("---")

    # ABOUT Dropdown
    st.markdown('<p class="sidebar-section-title">📂 ABOUT</p>', unsafe_allow_html=True)
    categories = get_all_categories(faq_data)
    selected_category = st.selectbox(
        "Select a topic",
        ["All Topics"] + categories,
        label_visibility="collapsed",
    )

    if selected_category != "All Topics":
        cat_questions = []
        cat_question_ids = []
        for cat in faq_data["faq_categories"]:
            if cat["category"] == selected_category:
                cat_questions = [q["question"] for q in cat["questions"]]
                cat_question_ids = [q["id"] for q in cat["questions"]]
                break
        for idx, q in enumerate(cat_questions[:6]):
            if st.button(f"💬 {q[:55]}...", key=f"cat_{cat_question_ids[idx]}", use_container_width=True):
                st.session_state.pending_quick_reply = q

    st.markdown("---")

    # COURSES Filter
    st.markdown('<p class="sidebar-section-title">🎓 COURSES</p>', unsafe_allow_html=True)
    selected_course = st.selectbox(
        "Select Course",
        ["All Courses", "Diploma", "B.TECH", "M.TECH"],
        label_visibility="collapsed",
    )

    COURSE_BRANCHES = {
        "Diploma": ["All Branches", "CSE"],
        "B.TECH":  ["All Branches", "CSE", "AIDS", "CSM", "CSD", "CSC", "CAI"],
        "M.TECH":  ["All Branches", "CSE", "AIML"],
    }

    selected_branch = "All Branches"
    if selected_course in COURSE_BRANCHES:
        st.markdown('<p class="sidebar-section-title">🌿 BRANCHES</p>', unsafe_allow_html=True)
        selected_branch = st.selectbox(
            "Select Branch",
            COURSE_BRANCHES[selected_course],
            label_visibility="collapsed",
        )

    st.markdown("---")

    st.markdown('<p class="sidebar-section-title">📅 Admission Timeline</p>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="sidebar-info-box">
            ⏳ <span style="color:#ffb300; font-weight:600;">Applications Open</span><br>
            📅 Academic Year 2026 - 2027<br>
            ℹ️ <em>Select your course above to match specific counseling dates.</em>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    st.markdown('<p class="sidebar-section-title">🏫 Links</p>', unsafe_allow_html=True)
    st.markdown(
        """
        🌐 [kietgroup.com](https://www.kietgroup.com/)  
        🔗 [Admissions Portal](https://www.kietgroup.com/admissions.php)
        """
    )

    st.markdown("---")

    st.markdown('<p class="sidebar-section-title">📊 Knowledge Base</p>', unsafe_allow_html=True)
    total_q = sum(len(c["questions"]) for c in faq_data["faq_categories"])
    total_cats = len(faq_data["faq_categories"])
    st.markdown(f"- **{total_q}** questions indexed")
    st.markdown(f"- **{total_cats}** topic categories")

# ─────────────────────────── Main Header ─────────────────────────────
logo_html = (
    f'<img src="data:image/png;base64,{logo_base64}" class="kiet-logo">'
    if logo_base64 else '<div style="font-size:2.5rem;">🎓</div>'
)

st.markdown(
    f"""
    <div class="kiet-header">
        {logo_html}
        <div>
            <h1>KIET Admissions Assistant</h1>
            <p>Your official guide for admissions at Kakinada Institute of Engineering &amp; Technology</p>
        </div>
        <div style="margin-left:auto;">
            <span class="kiet-badge">AI Assistant</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Metric cards
m_col1, m_col2, m_col3 = st.columns(3)
with m_col1:
    st.markdown('<div class="metric-container"><div class="metric-val">45 LPA</div><div class="metric-lbl">🚀 Highest Package</div></div>', unsafe_allow_html=True)
with m_col2:
    st.markdown('<div class="metric-container"><div class="metric-val">A+ Grade</div><div class="metric-lbl">🏆 NAAC Accreditation</div></div>', unsafe_allow_html=True)
with m_col3:
    st.markdown('<div class="metric-container"><div class="metric-val">100+ Companies</div><div class="metric-lbl">💼 Prime Recruiters</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

st.markdown(
    """
    <div class="disclaimer-box">
        ⚠️ <strong>Note:</strong> This chatbot answers from our official FAQ database.
        For current fee figures, timelines, and seat availability, always verify details with the
        <strong>KIET Admissions Office</strong>.
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Context reminder ──────────────────────────────────────────────────
context_reminder = ""
if selected_course != "All Courses":
    context_reminder = f" (Focusing explicitly on the {selected_course} program"
    if selected_branch != "All Branches":
        context_reminder += f" within the {selected_branch} branch"
    context_reminder += ")"

# ─────────────────────────── Persona Selection ───────────────────────
if st.session_state["persona"] is None and not active_session["history"]:
    st.markdown("### 👋 Welcome! Who are you?")
    st.markdown('<p style="color:#8a8a93; font-size:0.9rem;">Help me personalize your experience by telling me a bit about yourself.</p>', unsafe_allow_html=True)

    p_col1, p_col2, p_col3 = st.columns(3)
    persona_map = {
        "🎓 New Applicant": p_col1,
        "📚 Existing Student": p_col2,
        "👨‍👩‍👧 Parent / Guardian": p_col3,
    }
    for persona_name, col in persona_map.items():
        with col:
            emoji = persona_name.split(" ")[0]
            label_parts = persona_name.split(" ", 1)
            sub_map = {
                "🎓 New Applicant": "Exploring admission",
                "📚 Existing Student": "Already enrolled",
                "👨‍👩‍👧 Parent / Guardian": "Enquiring for ward",
            }
            if st.button(f"{persona_name}", key=f"persona_{persona_name}", use_container_width=True):
                st.session_state["persona"] = persona_name
                st.rerun()
    st.markdown("---")

# ─────────────────────────── Chat History ────────────────────────────
history = active_session["history"]

# Render existing messages with feedback buttons
for idx, msg in enumerate(history):
    with st.chat_message(msg["role"], avatar="🧑‍🎓" if msg["role"] == "user" else "🎓"):
        display_content = msg["content"].split(" [Context constraint:")[0]
        st.markdown(display_content)

        # Show feedback row after each assistant message
        if msg["role"] == "assistant":
            fb_key = f"{curr_id}_{idx}"
            given = st.session_state["feedback_given"].get(fb_key)

            if given is None:
                fb_col1, fb_col2, fb_col3 = st.columns([0.08, 0.08, 0.84])
                with fb_col1:
                    if st.button("👍", key=f"up_{fb_key}", help="Helpful"):
                        st.session_state["feedback_given"][fb_key] = "up"
                        # Find the preceding user message
                        user_q = history[idx-1]["content"] if idx > 0 else ""
                        save_feedback(user_q, msg["content"], "thumbs_up")
                        st.rerun()
                with fb_col2:
                    if st.button("👎", key=f"dn_{fb_key}", help="Not helpful"):
                        st.session_state["feedback_given"][fb_key] = "down"
                        user_q = history[idx-1]["content"] if idx > 0 else ""
                        save_feedback(user_q, msg["content"], "thumbs_down")
                        st.rerun()
            elif given == "up":
                st.markdown('<span style="color:#23a55a; font-size:0.8rem;">✅ Thanks for your feedback!</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span style="color:#f28b82; font-size:0.8rem;">🙏 Sorry about that! We\'ll improve.</span>', unsafe_allow_html=True)

# ── Welcome message ───────────────────────────────────────────────────
if not history and not active_session["greeted"] and st.session_state["persona"]:
    persona = st.session_state["persona"]
    config = PERSONA_CONFIG[persona]

    with st.chat_message("assistant", avatar="🎓"):
        st.markdown(f"👋 **{config['greeting']}**{context_reminder}")

        f_col1, f_col2 = st.columns(2)
        with f_col1:
            st.markdown("""
                <div class="feature-card">
                    <div class="feature-title">🎓 Admissions &amp; Criteria</div>
                    <div class="feature-desc">Cutoffs, counseling schedules, and seat allocations.</div>
                </div>""", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("""
                <div class="feature-card">
                    <div class="feature-title">🏠 Accommodations &amp; Transit</div>
                    <div class="feature-desc">Room layouts, dining, safety, and bus routes.</div>
                </div>""", unsafe_allow_html=True)
        with f_col2:
            st.markdown("""
                <div class="feature-card">
                    <div class="feature-title">💰 Tuition &amp; Scholarships</div>
                    <div class="feature-desc">Fee structures, installments, and government waivers.</div>
                </div>""", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("""
                <div class="feature-card">
                    <div class="feature-title">📄 Documents Checklist</div>
                    <div class="feature-desc">All documents needed to clear verification.</div>
                </div>""", unsafe_allow_html=True)

    active_session["greeted"] = True

st.markdown("<br>", unsafe_allow_html=True)

# ── Starter chips ─────────────────────────────────────────────────────
if not history and st.session_state["persona"]:
    persona = st.session_state["persona"]
    starter_questions = PERSONA_CONFIG[persona]["starters"]

    st.markdown("**🚀 Popular Questions — click to ask:**")
    cols = st.columns(4)
    for i, q in enumerate(starter_questions):
        with cols[i % 4]:
            if st.button(q, key=f"starter_{i}", use_container_width=True):
                st.session_state.pending_quick_reply = q
                st.rerun()

    st.markdown("---")
    st.markdown("### 📌 Frequently Reviewed Inquiries")
    with st.expander("📄 What documents are mandatory during verification counseling?"):
        st.markdown("Candidates must bring their Rank Card, Hall Ticket, Intermediate Marks Memo, SSC Certificate, Study Certificates from class 6 to Intermediate, Transfer Certificate (TC), and Caste/Income certificates if applicable.")
    with st.expander("🏠 What accommodations are offered in the campus hostels?"):
        st.markdown("KIET provides separate hostel complexes for boys and girls with full security, mineral water systems, nutritious dining halls, recreation lounges, and round-the-clock Wi-Fi facilities.")
    with st.expander("🚌 Is college bus transport available across local routes?"):
        st.markdown("Yes, the institution operates a comprehensive fleet of buses covering major towns across Kakinada, Rajahmundry, Ramachandrapuram, and adjoining rural centers.")

# ─────────────────────────── Response Handler ────────────────────────

def handle_response(user_raw: str):
    """Shared logic: append user msg, stream response, log if needed."""
    if len(active_session["history"]) == 0:
        active_session["title"] = user_raw.split(" [Context constraint:")[0][:40]

    if selected_course != "All Courses":
        user_input = user_raw + f" [Context constraint: Provide answer specific to {selected_course} course, branch: {selected_branch}]"
    else:
        user_input = user_raw

    active_session["history"].append({"role": "user", "content": user_input})

    with st.chat_message("user", avatar="🧑‍🎓"):
        st.markdown(user_raw)

    with st.chat_message("assistant", avatar="🎓"):
        # Typing indicator while streaming starts
        typing_ph = st.empty()
        typing_ph.markdown(
            """
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <span style="margin-left:6px;">KIET Assistant is typing…</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        response_ph = st.empty()
        full_response = ""
        first_chunk = True
        try:
            for chunk in get_bot_response_stream(
                user_input,
                active_session["history"][:-1],
                faq_data,
            ):
                if first_chunk:
                    typing_ph.empty()
                    first_chunk = False
                full_response += chunk
                response_ph.markdown(full_response + "▌")
            response_ph.markdown(full_response)
        except Exception as e:
            typing_ph.empty()
            full_response = (
                f"⚠️ I encountered an error: `{str(e)}`\n\n"
                "Please check your configurations and try again."
            )
            response_ph.markdown(full_response)

        # ── Unanswered question logging ───────────────────────────────
        if is_low_confidence(full_response):
            log_unanswered_question(user_raw, full_response)

        # ── "Did you mean?" suggestions ───────────────────────────────
        if is_low_confidence(full_response):
            related = get_related_questions(user_raw, faq_data, top_n=3)
            if related:
                st.markdown(
                    '<div class="dym-container">'
                    '<div class="dym-title">🔍 Did you mean one of these?</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )
                for rq in related:
                    if st.button(f"💬 {rq[:70]}", key=f"dym_{hash(rq)}", use_container_width=False):
                        st.session_state.pending_quick_reply = rq
                        st.rerun()

    active_session["history"].append({"role": "assistant", "content": full_response})
    st.rerun()

# ── Handle quick reply ────────────────────────────────────────────────
if st.session_state.pending_quick_reply:
    user_raw = st.session_state.pending_quick_reply
    st.session_state.pending_quick_reply = None
    handle_response(user_raw)

# ── Main chat input ───────────────────────────────────────────────────
user_input = st.chat_input("Ask about admissions, fees, hostel, placements...")

if user_input:
    if is_empty_or_whitespace(user_input):
        st.warning("Please type a question.")
    else:
        user_input = sanitize_input(user_input)
        # Auto-set persona if still None
        if st.session_state["persona"] is None:
            st.session_state["persona"] = "🎓 New Applicant"
        handle_response(user_input)

# ── Help Desk Banner ──────────────────────────────────────────────────
st.markdown(
    """
    <div class="helpdesk-banner">
        <div>
            <strong style="color:#ffffff; font-size:0.95rem;">Need to speak with a counselor?</strong><br>
            <span style="color:#8a8a93; font-size:0.82rem;">Our admissions division is operational Monday through Saturday, 9:00 AM to 5:00 PM.</span>
        </div>
        <div style="text-align:right; font-size:0.9rem; color:#ffb300; font-weight:600;">
            📞 +91 94411 25143
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)