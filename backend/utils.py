"""
Utility functions for the KIET FAQ Chatbot.
Handles FAQ loading, search, and helper operations.
"""

import json
import os
import re
from pathlib import Path


FAQ_PATH = Path(__file__).parent.parent / "data" / "faq.json"


def load_faq_data(path: Path = FAQ_PATH) -> dict:
    """Load and return the FAQ knowledge base from JSON."""
    if not path.exists():
        raise FileNotFoundError(f"FAQ data file not found at: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_all_categories(faq_data: dict) -> list[str]:
    """Return all category names from the FAQ data."""
    return [cat["category"] for cat in faq_data.get("faq_categories", [])]


def get_questions_by_category(faq_data: dict, category_name: str) -> list[dict]:
    """Return all questions under a specific category."""
    for cat in faq_data.get("faq_categories", []):
        if cat["category"].lower() == category_name.lower():
            return cat.get("questions", [])
    return []


def search_faq(faq_data: dict, query: str, max_results: int = 5) -> list[dict]:
    """
    Simple keyword-based FAQ search.
    Returns a ranked list of matching Q&A pairs.
    Useful as a fallback or to pre-filter context.
    """
    query_lower = query.lower()
    keywords = re.findall(r"\w+", query_lower)
    results = []

    for cat in faq_data.get("faq_categories", []):
        for item in cat.get("questions", []):
            score = 0
            q_lower = item["question"].lower()
            a_lower = item["answer"].lower()

            for kw in keywords:
                if kw in q_lower:
                    score += 3  # Higher weight for question match
                if kw in a_lower:
                    score += 1

            if score > 0:
                results.append({
                    "question": item["question"],
                    "answer": item["answer"],
                    "category": cat["category"],
                    "id": item.get("id", ""),
                    "related_questions": item.get("related_questions", []),
                    "score": score,
                })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:max_results]


def get_starter_questions(faq_data: dict) -> list[str]:
    """
    Return a curated list of starter/popular questions to show on chatbot launch.
    """
    starters = [
        "How can I get admission into KIET?",
        "What B.Tech courses are available?",
        "What is the fee structure?",
        "Does KIET have hostel facilities?",
        "What is the placement record?",
        "Are scholarships available?",
        "Can I join without AP EAPCET?",
        "What documents are required for admission?",
    ]
    return starters


def format_conversation_for_api(conversation_history: list[dict]) -> list[dict]:
    """
    Format Streamlit session state conversation history
    into the messages format required by the Anthropic API.
    """
    messages = []
    for msg in conversation_history:
        role = "user" if msg["role"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["content"]})
    return messages


def truncate_conversation_history(
    history: list[dict], max_turns: int = 10
) -> list[dict]:
    """
    Keep only the most recent N turns to avoid exceeding token limits.
    Always keeps the full history in session but sends a truncated version to API.
    """
    if len(history) <= max_turns * 2:
        return history
    return history[-(max_turns * 2):]


def is_empty_or_whitespace(text: str) -> bool:
    """Check if user input is empty or just whitespace."""
    return not text or not text.strip()


def is_too_vague(text: str) -> bool:
    """
    Detect overly vague queries that need clarification.
    """
    vague_patterns = [
        r"^tell me (about|more)$",
        r"^(what|how|tell).*college$",
        r"^(hi|hello|hey)$",
        r"^(info|information|details)$",
        r"^(help|assist)$",
    ]
    text_clean = text.strip().lower()
    for pattern in vague_patterns:
        if re.match(pattern, text_clean):
            return True
    # Very short query with no context
    if len(text_clean.split()) <= 2 and not any(
        kw in text_clean
        for kw in ["fee", "hostel", "rank", "date", "exam", "seat", "nri", "mba", "mca", "ai"]
    ):
        return False
    return False


def sanitize_input(text: str) -> str:
    """Basic input sanitization — strip extra whitespace."""
    return " ".join(text.split())