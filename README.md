# 🎓 KIET College Admission FAQ Chatbot

> An AI-powered admissions assistant for **Kakinada Institute of Engineering and Technology (KIET)** — built with Streamlit and the Anthropic Claude API.
LIVE DEMO:https://kiet-college-admission-faq-chatbot-k9tmbywzvcgmsnehxwtvfq.streamlit.app/
---

## 📸 Features

- **Grounded answers** — The bot answers *only* from the official FAQ knowledge base. It will never hallucinate fees, ranks, or dates.
- **Streaming responses** — Real-time typing effect for a natural conversation feel.
- **Quick-reply chips** — Popular questions surface on load; related questions suggested after each answer.
- **Category browser** — Sidebar lets users drill into a specific topic (Hostel, Placements, Fees, etc.).
- **Conversation memory** — Follow-up questions work naturally; context is maintained across the session.
- **Graceful fallback** — Questions not in the FAQ get a clear "contact admissions" message instead of guesses.
- **API key validation** — One-click health check from the sidebar.

---

## 🗂️ Project Structure

```
College-FAQ-Bot/
│
├── app.py                  ← Streamlit UI + chat logic (entry point)
│
├── data/
│   └── faq.json            ← Full FAQ knowledge base (18 categories, 130+ Q&A)
│
├── backend/
│   ├── __init__.py
│   ├── api_handler.py      ← Anthropic API calls + streaming
│   ├── prompts.py          ← System prompt construction
│   └── utils.py            ← FAQ loading, search, helpers
│
├── .env.example            ← Copy → .env and add your API key
├── .gitignore              ← Keeps .env out of Git
├── requirements.txt
└── README.md
```

---

## ⚙️ Setup & Run Locally

### Prerequisites
- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/)

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/College-FAQ-Bot.git
cd College-FAQ-Bot

# 2. Create and activate a virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up your API key
cp .env.example .env
# Open .env and replace the placeholder with your real API key:
# ANTHROPIC_API_KEY=sk-ant-...

# 5. Run the app
streamlit run app.py
```

The app opens at **http://localhost:8501** in your browser.

---

## 🔑 API Key Security

| ✅ Do | ❌ Don't |
|---|---|
| Store key in `.env` file | Hardcode key in any `.py` file |
| Add `.env` to `.gitignore` | Push `.env` to GitHub |
| Use platform secrets for hosting | Share key in public repos or chats |

---

## 🧠 How It Works

1. **Knowledge Base (`data/faq.json`)** — 130+ Q&A pairs across 18 categories, each with a unique ID and related question links.

2. **System Prompt (`backend/prompts.py`)** — Injects the entire FAQ into Claude's context as a grounded knowledge base. Instructs Claude to refuse to answer from general knowledge and always redirect unknown questions to the admissions office.

3. **API Handler (`backend/api_handler.py`)** — Manages conversation history, token truncation, and streaming.

4. **Streamlit UI (`app.py`)** — Chat interface with quick-reply chips, category browser sidebar, and styled message bubbles.

---

## 🧪 Test Cases

| # | User Message | Expected Behavior |
|---|---|---|
| 1 | What B.Tech courses are available? | Lists AI, AI & ML, Data Science, Cyber Security, etc. |
| 2 | What is the fee for B.Tech? | Directs to admissions office for exact figures |
| 3 | Does KIET have hostel for girls? | Confirms yes, separate hostels for boys and girls |
| 4 | What is the highest placement package? | States up to 45 LPA |
| 5 | Can I join without AP EAPCET? | Explains management quota option |
| 6 | Are scholarships available for SC students? | Confirms yes under eligible government schemes |
| 7 | What documents do I need? | Lists all required documents |
| 8 | Is ragging allowed? | Strict no, explains anti-ragging policy |
| 9 | What is the weather like near KIET? | Fallback: "I don't have info... contact admissions" |
| 10 | What is KIET's NAAC grade? | Fallback: "I don't have info... contact admissions" |

---

## 👥 Team Role Split

| Member | Role |
|---|---|
| **Member 1** | Knowledge base creation — `data/faq.json` |
| **Member 2** | System prompt engineering — `backend/prompts.py` |
| **Member 3** | Chatbot UI — `app.py` styling & layout |
| **Member 4** | API integration — `backend/api_handler.py` |
| **Member 5** | Testing, deployment, README |

---

## 🚀 Deployment

Deploy on **Streamlit Community Cloud** (free):

1. Push code to a public GitHub repo (ensure `.env` is in `.gitignore`).
2. Go to [share.streamlit.io](https://share.streamlit.io) → New App.
3. Select your repo and set `app.py` as the entry point.
4. Under **Advanced Settings → Secrets**, add:
   ```
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
5. Deploy. Your app gets a public URL instantly.

---

## 📝 Important Notes

- **Do NOT let the AI answer from general knowledge.** The system prompt enforces strict grounding — if a fact isn't in `faq.json`, the bot redirects to the admissions office.
- Keep `faq.json` updated whenever the institution updates its data.
- The conversation history is session-scoped and does not persist across page refreshes.
