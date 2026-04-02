# ============================================================
#  END-TO-END CONFIGURATION GUIDE
#  Municipal WhatsApp Chatbot — Ahilyanagar Mahanagar Palika
# ============================================================

## 📁 Complete Folder Structure

```
whatsapp_bot/
├── .env.example              ← COPY to .env and fill in your values
├── .env                      ← YOUR secrets (never commit this)
├── requirements.txt          ← Python dependencies
├── Dockerfile                ← Container build
├── docker-compose.yml        ← Local infra (Postgres + Redis + Bot)
├── CONFIGURATION.md          ← THIS FILE
├── DEPLOYMENT.md             ← How to run locally & in production
│
├── flows/
│   └── flow.json             ← ⭐ ENTIRE CHATBOT LOGIC LIVES HERE
│                                Add menus, change text, add departments
│                                — no Python code changes needed
│
├── app/
│   ├── main.py               ← FastAPI app entry point
│   │
│   ├── core/
│   │   ├── config.py         ← Reads .env into typed Settings object
│   │   └── logging.py        ← Structured logging (JSON in prod)
│   │
│   ├── api/
│   │   ├── webhook.py        ← GET /webhook (verify) + POST /webhook (messages)
│   │   └── admin.py          ← Admin REST endpoints (stats, complaint status)
│   │
│   ├── db/
│   │   └── models.py         ← SQLAlchemy ORM: users, sessions, complaints, logs
│   │
│   └── services/
│       ├── flow_engine.py    ← State machine: reads flow.json, drives transitions
│       ├── session_manager.py← Redis cache + Postgres session persistence
│       ├── message_processor.py ← Orchestrates the full incoming-message pipeline
│       ├── whatsapp_sender.py← Calls WhatsApp Cloud API to send replies
│       └── complaint_service.py ← Saves complaint to DB, generates complaint IDs
│
├── scripts/
│   ├── schema.sql            ← Full Postgres schema (run once at setup)
│   └── setup_db.sh           ← Helper script to create DB + run schema
│
└── tests/
    ├── test_flow_engine.py   ← 27 unit tests (flow logic, no DB needed)
    ├── test_webhook.py       ← Webhook parsing tests
    └── sample_payloads.json  ← Real WhatsApp API payload examples
```

---

## 🔑 STEP 1 — Configure Your Credentials (.env)

Copy `.env.example` to `.env` and fill in every value:

```bash
cp .env.example .env
```

### WhatsApp Cloud API credentials

```env
WHATSAPP_PHONE_NUMBER_ID=123456789012345
WHATSAPP_ACCESS_TOKEN=EAAxxxxxxxxxxxxxx
WHATSAPP_VERIFY_TOKEN=my_secret_verify_token_abc123
WHATSAPP_API_VERSION=v19.0
```

**Where to get these:**
1. Go to https://developers.facebook.com → My Apps → Create App → Business
2. Add "WhatsApp" product
3. Under WhatsApp → API Setup:
   - Copy **Phone Number ID** → `WHATSAPP_PHONE_NUMBER_ID`
   - Generate/copy **Temporary or Permanent Token** → `WHATSAPP_ACCESS_TOKEN`
4. Under Webhooks → make up any random string → `WHATSAPP_VERIFY_TOKEN`
   (e.g. `openssl rand -hex 20`)

### Database

```env
DATABASE_URL=postgresql+asyncpg://botuser:botpass@localhost:5432/ampbot
```

For production (e.g. Supabase / AWS RDS), replace with your connection string:
```env
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/DBNAME
```

### Redis

```env
REDIS_URL=redis://localhost:6379/0
SESSION_TTL_SECONDS=86400
```

For production (e.g. Upstash / ElastiCache):
```env
REDIS_URL=redis://:PASSWORD@HOST:6379/0
```

### App settings

```env
APP_ENV=production        # Use 'development' for verbose logs + Swagger UI
LOG_LEVEL=INFO
MAX_FALLBACK_RETRIES=3    # Invalid inputs before human escalation
FLOW_FILE=flows/flow.json
```

### Municipality info

```env
MUNICIPALITY_NAME=Ahilyanagar Mahanagar Palika
MUNICIPALITY_PHONE=02412345678
```

---

## 🏛️ STEP 2 — Customise the Chatbot (flows/flow.json)

**This is the only file you need to edit to change chatbot behaviour.**
No Python code changes are ever required for content/menu changes.

### Change the welcome message

Find the `"START"` node:
```json
"START": {
  "messages": {
    "mr": "🙏 नमस्कार *{name}*\nWelcome to YOUR MUNICIPALITY NAME...",
    "en": "🙏 Hello *{name}*\nWelcome to YOUR MUNICIPALITY NAME..."
  }
}
```
Replace the text. `{name}` is replaced automatically with the user's WhatsApp display name.

### Change municipality name in all messages

Search-and-replace `Ahilyanagar Mahanagar Palika` with your municipality name
across the entire `flow.json`.

### Add a new main menu item

In the `MAIN_MENU` node, add to the `"options"` array:
```json
{
  "id": "menu_9",
  "title": { "mr": "नवीन सेवा", "en": "New Service" },
  "description": { "mr": "सेवेचे वर्णन", "en": "Service description" },
  "next": "NEW_SERVICE_NODE"
}
```
Then add the target node anywhere in `"nodes"`:
```json
"NEW_SERVICE_NODE": {
  "id": "NEW_SERVICE_NODE",
  "type": "text_with_buttons",
  "messages": {
    "mr": "📋 नवीन सेवेची माहिती येथे...",
    "en": "📋 New service info here..."
  },
  "options": [
    { "id": "main_menu", "title": { "mr": "मुख्य मेनू", "en": "Main Menu" }, "next": "MAIN_MENU" }
  ]
}
```

### Add a new government scheme

In the `SCHEMES` node's `"options"` array:
```json
{
  "id": "scheme_new",
  "title": { "mr": "नवीन योजना", "en": "New Scheme" },
  "description": { "mr": "योजना वर्णन", "en": "Scheme description" },
  "next": "SCHEME_NEW"
}
```
Add the scheme detail node:
```json
"SCHEME_NEW": {
  "id": "SCHEME_NEW",
  "type": "text_with_buttons",
  "messages": {
    "mr": "📋 *नवीन योजना*\n\nयोजनेची माहिती येथे.\n\n🌐 https://scheme-website.gov.in",
    "en": "📋 *New Scheme*\n\nScheme details here.\n\n🌐 https://scheme-website.gov.in"
  },
  "options": [
    { "id": "back_schemes", "title": { "mr": "मागे जा", "en": "Go Back" }, "next": "SCHEMES" },
    { "id": "main_menu",    "title": { "mr": "मुख्य मेनू", "en": "Main Menu" }, "next": "MAIN_MENU" }
  ]
}
```

### Add a new ward (Prabhag)

In `COMPLAINT_WARD` → `"options"`:
```json
{
  "id": "ward_5",
  "title": { "mr": "प्रभाग समिती क्रमांक 5", "en": "Ward Committee 5" },
  "description": { "mr": "नवीन क्षेत्र", "en": "New Area" },
  "next": "COMPLAINT_TYPE"
}
```
And in `"officer_map"`:
```json
"ward_5": {
  "name": "श्री. नवीन अधिकारी",
  "designation": {
    "mr": "क्षेत्रिय अधिकारी, प्र.स.क्र. ०५",
    "en": "Field Officer, Ward 5"
  },
  "phone": "9800000000"
}
```

### Add a new complaint department

In `COMPLAINT_TYPE` → `"options"`:
```json
{
  "id": "dept_road",
  "title": { "mr": "रस्ते विभाग", "en": "Roads Department" },
  "description": { "mr": "रस्त्याच्या तक्रारी", "en": "Road complaints" },
  "next": "COMPLAINT_SUBTYPE"
}
```
In `COMPLAINT_SUBTYPE` → `"subtypes"`:
```json
"dept_road": [
  { "id": "r1", "title": { "mr": "खड्डे",       "en": "Potholes" },         "next": "COMPLAINT_CONFIRM" },
  { "id": "r2", "title": { "mr": "रस्ता खराब",  "en": "Damaged road" },      "next": "COMPLAINT_CONFIRM" },
  { "id": "r3", "title": { "mr": "दिवे नाही",   "en": "No streetlights" },   "next": "COMPLAINT_CONFIRM" },
  { "id": "r_other", "title": { "mr": "इतर",     "en": "Other" },             "next": "COMPLAINT_FREETEXT" }
]
```

### Change officer phone numbers

In `"officer_map"` at the bottom of `flow.json`:
```json
"officer_map": {
  "ward_1": { "name": "Officer Name", "phone": "9XXXXXXXXX" },
  "ward_2": { "name": "Officer Name", "phone": "9XXXXXXXXX" },
  ...
}
```

### Change emergency numbers

In the `"EMERGENCY"` node, edit the message text directly.

### Add a third language (e.g., Hindi)

1. In all node `"messages"`, add `"hi": "..."` alongside `"mr"` and `"en"`
2. In `"START"` node options, add:
   ```json
   { "id": "lang_hi", "title": "हिंदी", "next": "MAIN_MENU" }
   ```
3. In `flow_engine.py` → `process()`, handle `lang_hi` → `sess["language"] = "hi"`

---

## 🗄️ STEP 3 — Database Setup

### Local (Docker)
```bash
docker-compose up postgres -d
psql postgresql://botuser:botpass@localhost:5432/ampbot -f scripts/schema.sql
```

### Production (manual)
```bash
# Connect to your Postgres instance
psql -U postgres -h YOUR_HOST

# Run inside psql:
CREATE USER botuser WITH PASSWORD 'your_strong_password';
CREATE DATABASE ampbot OWNER botuser;
GRANT ALL PRIVILEGES ON DATABASE ampbot TO botuser;
\q

# Run schema
psql postgresql://botuser:your_strong_password@YOUR_HOST:5432/ampbot -f scripts/schema.sql
```

---

## 📊 STEP 4 — Complaint ID Format

Complaints are auto-generated as: `AMP-YYYYMMDD-XXXX`

Example: `AMP-20260401-0001`

To change the prefix from `AMP` to your municipality code, edit `scripts/schema.sql`:
```sql
-- Find this line:
RETURN 'AMP-' || today || '-' || LPAD(seq_val::TEXT, 4, '0');

-- Change to e.g.:
RETURN 'NP-' || today || '-' || LPAD(seq_val::TEXT, 4, '0');
```

---

## 🔔 STEP 5 — Connect WhatsApp Webhook

After starting the server:

```bash
# Expose locally with ngrok
ngrok http 8000

# Your webhook URL will be:
# https://XXXX.ngrok.io/webhook
```

In Meta Developer Console:
1. WhatsApp → Configuration → Webhook
2. Callback URL: `https://YOUR_DOMAIN/webhook`
3. Verify Token: same value as `WHATSAPP_VERIFY_TOKEN` in `.env`
4. Click **Verify and Save**
5. Subscribe to: `messages`

---

## 🛠️ STEP 6 — Admin API

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Server liveness check |
| `/admin/stats` | GET | Total users, complaints, open count |
| `/admin/complaints/{id}` | GET | Full complaint detail |
| `/admin/complaints/{id}/status` | PATCH | Update status: `open` / `acknowledged` / `in_progress` / `resolved` / `closed` |
| `/docs` | GET | Swagger UI (development mode only) |

Example:
```bash
curl http://localhost:8000/admin/complaints/AMP-20260401-0001
curl -X PATCH "http://localhost:8000/admin/complaints/AMP-20260401-0001/status?status=resolved"
```

---

## ⚙️ STEP 7 — Production Tuning

### Scale workers
```bash
# In Dockerfile CMD or directly:
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
# Rule of thumb: 1 worker per CPU core
```

### Nginx reverse proxy (recommended)
```nginx
server {
    listen 443 ssl;
    server_name bot.yourdomain.com;

    location /webhook {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Enable request signature verification
In `app/api/webhook.py`, uncomment the `_verify_signature(request, body)` call
in `receive_webhook()`. This validates the `X-Hub-Signature-256` header
from Meta to block spoofed requests.

### Persistent access token
Temporary tokens expire in 24h. Generate a **System User permanent token**:
Meta Business Suite → Settings → System Users → Generate Token → assign WhatsApp permissions.

---

## 🧪 Testing Without WhatsApp

Use the payloads in `tests/sample_payloads.json`:

```bash
# Simulate a user sending "hi"
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d @tests/sample_payloads.json | python -m json.tool

# Run all unit tests (no DB/Redis needed)
pytest tests/test_flow_engine.py -v
```

---

## ❓ Common Issues

| Problem | Fix |
|---|---|
| Webhook verification fails | Check `WHATSAPP_VERIFY_TOKEN` matches Meta console exactly |
| Messages not sending | Check `WHATSAPP_ACCESS_TOKEN` is valid; look at logs for 401/400 errors |
| Session not persisting | Check Redis is running: `redis-cli ping` |
| Complaint not saving | Check Postgres is running and schema was applied |
| Bot sends English when Marathi selected | Check `lang_mr` button ID matches flow.json START node option id |
| `generate_complaint_id` function missing | Re-run `scripts/schema.sql` — the function must exist in Postgres |
