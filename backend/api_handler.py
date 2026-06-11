"""
API handler for the KIET FAQ Chatbot.
Uses Groq (free tier) — fast inference with Llama models.
"""

import os
from groq import Groq
from dotenv import load_dotenv

from backend.prompts import build_system_prompt
from backend.utils import truncate_conversation_history

load_dotenv()

GROQ_MODEL = "llama-3.1-8b-instant"  # Lightweight, fast, efficient for FAQ responses


def get_groq_client() -> Groq:
    """Initialize Groq client using API key from .env."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY not found. Please add it to your .env file.\n"
            "Get your free key at: https://console.groq.com"
        )
    return Groq(api_key=api_key)


def _build_messages(system_prompt: str, conversation_history: list, user_message: str) -> list:
    """Build the full messages list for Groq API."""
    messages = [{"role": "system", "content": system_prompt}]
    for msg in conversation_history:
        role = "user" if msg["role"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})
    return messages


def get_bot_response_stream(user_message: str, conversation_history: list, faq_data: dict):
    """
    Streaming response using Groq.
    Yields text chunks for real-time typing effect in UI.
    """
    client = get_groq_client()
    system_prompt = build_system_prompt(faq_data)
    trimmed_history = truncate_conversation_history(conversation_history, max_turns=10)
    messages = _build_messages(system_prompt, trimmed_history, user_message)

    stream = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        max_tokens=1024,
        temperature=0.3,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def get_bot_response(user_message: str, conversation_history: list, faq_data: dict):
    """
    Non-streaming response — useful for testing.
    Returns (bot_reply_text, updated_conversation_history).
    """
    client = get_groq_client()
    system_prompt = build_system_prompt(faq_data)
    trimmed_history = truncate_conversation_history(conversation_history, max_turns=10)
    messages = _build_messages(system_prompt, trimmed_history, user_message)

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        max_tokens=1024,
        temperature=0.3,
    )

    bot_reply = response.choices[0].message.content.strip()

    updated_history = conversation_history + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": bot_reply},
    ]
    return bot_reply, updated_history


def validate_api_key() -> tuple:
    """Validate Groq API key. Returns (is_valid, message)."""
    try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=10,
        )
        if response.choices[0].message.content:
            return True, "Groq API key is valid."
        return False, "Unexpected response from Groq."
    except EnvironmentError as e:
        return False, str(e)
    except Exception as e:
        error_msg = str(e)
        if "invalid_api_key" in error_msg.lower() or "401" in error_msg:
            return False, "Invalid API key. Check your .env file."
        return False, f"API error: {error_msg}"