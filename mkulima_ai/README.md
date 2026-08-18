# 🌱 Mkulima AI Tanzania – WhatsApp Bot

WhatsApp bot ya ushauri wa kilimo kwa wakulima wa Tanzania.
Imejengwa na **JamiiTek Digital Agency**, Dar es Salaam.

## Stack
- **Backend:** Django 4.2 (Python)
- **Database:** PostgreSQL (Supabase) / SQLite (development)  
- **WhatsApp:** Meta WhatsApp Business Cloud API
- **AI Engine:** Claude AI (Anthropic) — kwa maswali ngumu
- **Deployment:** Render.com

## Mtiririko wa Mfumo (System Flow)
```
Mkulima → WhatsApp → Webhook → Text/Voice Detection
→ Normalize → Synonyms → Crop Detection → Location Detection
→ Zone Mapping → Intent Detection → Knowledge Retrieval
→ Answer Template / Claude AI → Follow-up Logic
→ WhatsApp Response → Log → Analytics
```

## Kuanza (Development)

```bash
# 1. Unzip na ingia kwenye folder
cd mkulima_ai

# 2. Tengeneza virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

# 3. Install packages
pip install -r requirements.txt

# 4. Copy env file
copy .env.example .env       # Windows
cp .env.example .env         # Mac/Linux
# Edit .env na credentials zako

# 5. Run migrations
python manage.py migrate

# 6. Ingiza data ya mwanzo
python scripts/seed_data.py

# 7. Run server
python manage.py runserver
```

## URLs
| URL | Maelezo |
|-----|---------|
| http://localhost:8000/dashboard/ | Admin Dashboard |
| http://localhost:8000/dashboard/login/ | Login |
| http://localhost:8000/dashboard/test-bot/ | Jaribu Bot |
| http://localhost:8000/dashboard/csv-import/ | Import CSV |
| http://localhost:8000/dashboard/analytics/ | Analytics |
| http://localhost:8000/admin/ | Django Admin |
| http://localhost:8000/webhook/whatsapp/ | WhatsApp Webhook |
| POST http://localhost:8000/api/test-message/ | Test API |

## Credentials za Default
- **Username:** `admin`
- **Password:** `Mkulima@2024`
⚠️ Badilisha password mara moja baada ya kuingia!

## Test Bot (API)
```bash
curl -X POST http://localhost:8000/api/test-message/ \
  -H "Content-Type: application/json" \
  -d '{"phone":"255700000001","message":"Ni mbegu gani ya mahindi nipande Singida?"}'
```

## WhatsApp Webhook Setup
1. Meta for Developers → WhatsApp → Configuration
2. Callback URL: `https://yourdomain.com/webhook/whatsapp/`
3. Verify Token: thamani ya `WHATSAPP_VERIFY_TOKEN` kwenye .env
4. Subscribe: `messages`

## Claude AI Setup
1. Nenda https://console.anthropic.com
2. Tengeneza API key
3. Weka kwenye .env: `ANTHROPIC_API_KEY=sk-ant-...`
4. Bot itatumia Claude kwa maswali ambayo templates hazijashughulikia

## CSV Import
Dashboard → Import CSV inakuruhusu kupakia datasets bila developer:
- `maize_varieties.csv` — Aina za mbegu
- `maize_answer_templates.csv` — Majibu mapya
- `maize_synonyms.csv` — Maneno mbadala
- `maize_farmer_questions.csv` — Mifano ya maswali
- `location_mapping.csv` — Maeneo na zones

## Deploy Render.com
```
Build Command: ./build.sh
Start Command: gunicorn mkulima_ai.wsgi:application --bind 0.0.0.0:$PORT --workers 2
```
Weka environment variables kutoka .env kwenye Render dashboard.

---
**JamiiTek Digital Agency** | Dar es Salaam, Tanzania | 2024
