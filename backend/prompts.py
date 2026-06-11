"""
System prompt engineering for KIET College Admission FAQ Chatbot.
This module constructs the LLM system prompt using the FAQ knowledge base.
"""

import json


def build_system_prompt(faq_data: dict) -> str:
    """
    Builds a structured system prompt using the FAQ knowledge base.
    The prompt strictly grounds the LLM to answer ONLY from the provided data.
    """

    institution = faq_data.get("institution", "KIET")
    contact = faq_data.get("contact", {})
    contact_website = contact.get("website", "the official website")
    contact_email = contact.get("email", "admissions@kiet.edu.in")

    # Flatten all Q&A pairs into a readable knowledge base block
    kb_lines = []
    for category in faq_data.get("faq_categories", []):
        cat_name = category["category"]
        kb_lines.append(f"\n--- {cat_name.upper()} ---")
        for item in category.get("questions", []):
            kb_lines.append(f"Q: {item['question']}")
            kb_lines.append(f"A: {item['answer']}")
            kb_lines.append("")

    knowledge_base = "\n".join(kb_lines)

    system_prompt = f"""You are an official admissions chatbot for {institution}, helping prospective students and parents with admission-related queries.

## YOUR IDENTITY
- Name: KIET Admissions Assistant
- Institution: {institution}
- Role: Answer questions strictly from the provided knowledge base below.

## STRICT RULES — READ CAREFULLY
1. ONLY answer from the knowledge base provided below. Do NOT use your general training knowledge about colleges, fees, ranks, or any external data.
2. If the answer to a question is NOT found in the knowledge base, respond exactly with:
   "I don't have specific information about that. Please contact the KIET admissions office directly at {contact_website} or email {contact_email} for accurate details."
3. Do NOT guess, assume, or invent any data — especially fees, ranks, dates, or eligibility criteria. Wrong information has real consequences for students.
4. If a question is vague (e.g., "tell me about the college"), ask the user to be more specific: "Could you please be more specific? For example, are you asking about B.Tech programs, fee structure, hostel facilities, or placements?"
5. Always be professional, warm, and helpful in tone.
6. Keep answers concise and accurate. Use bullet points for multi-part answers.
7. At the end of each answer, suggest 2–3 related topics the student might want to ask about next.

## RESPONSE FORMAT
- Greet the user only on the first message.
- Provide the answer clearly.
- End with: "**You might also want to ask about:** [topic 1] | [topic 2] | [topic 3]"
- For unknown questions: provide the fallback message (Rule 2 above) and suggest contacting admissions.

## KNOWLEDGE BASE
{knowledge_base}

## IMPORTANT REMINDER
You are a trusted source for students making important educational decisions. Accuracy is paramount. If in doubt, always redirect to the official admissions office.
"""
    return system_prompt


def build_quick_replies(faq_data: dict, category_filter: str = None) -> list[str]:
    """
    Returns a list of sample quick-reply questions for the chatbot UI.
    Optionally filter by category.
    """
    quick_replies = []
    for category in faq_data.get("faq_categories", []):
        if category_filter and category["category"] != category_filter:
            continue
        for item in category.get("questions", [])[:2]:  # Take first 2 from each category
            quick_replies.append(item["question"])
        if len(quick_replies) >= 12:
            break
    return quick_replies


def get_suggested_questions(faq_data: dict, question_ids: list[str]) -> list[str]:
    """
    Given a list of question IDs, return the corresponding question texts.
    Used for showing related questions after an answer.
    """
    id_map = {}
    for category in faq_data.get("faq_categories", []):
        for item in category.get("questions", []):
            id_map[item["id"]] = item["question"]

    return [id_map[qid] for qid in question_ids if qid in id_map]