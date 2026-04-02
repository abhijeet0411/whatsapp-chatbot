# 🏛️ Municipal WhatsApp Chatbot

Production-ready WhatsApp chatbot for Indian municipal corporations (Nagar Palika / Mahanagar Palika).
Reverse-engineered from the Ahilyanagar Mahanagar Palika bot — fully customisable for any municipality.

## ✨ Features
- Bilingual (Marathi + English) with language selection at start
- 8-department main menu
- 5-step complaint registration with auto-generated IDs (e.g. `AMP-20260401-0001`)
- Government scheme info with official links
- Redis-backed sessions (24h TTL) + PostgreSQL persistence
- WhatsApp interactive buttons and list messages
- Automatic fallback + human escalation after 3 invalid inputs
- Admin REST API for complaint management
- Fully deterministic — zero AI/NLP, 100% menu-driven

## 🚀 Quick Start

```bash
cp .env.example .env          # Fill in your WhatsApp API credentials
docker-compose up -d          # Start Postgres + Redis
psql ... -f scripts/schema.sql  # Create tables
pip install -r requirements.txt
uvicorn app.main:app --reload  # Start bot on :8000
pytest tests/ -v               # Run 27 tests
```

## 📖 Documentation
- **CONFIGURATION.md** — Complete guide to customising every part of the bot
- **DEPLOYMENT.md** — Local + production deployment steps

## 🗂️ Key Files
| File | What to change |
|---|---|
| `flows/flow.json` | All menus, messages, officer names, departments |
| `.env` | API keys, DB URL, Redis URL |
| `scripts/schema.sql` | Complaint ID prefix, DB structure |
