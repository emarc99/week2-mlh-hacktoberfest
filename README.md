# SlipsLedger

Photo of a rent, utility, security, cleaner, or estate-dues slip → **Gemma 4** classifies and extracts → SQLite ledger + CSV.

Built for MLH Ibadan Hack Day / DEV Week 2. **Gemma is the core** — without the multimodal model call there is no product. Streamlit displays results; SQLite stores them; DigitalOcean App Platform hosts the demo.

## Problem

Paper and WhatsApp photo trails for recurring Nigerian compound payments are easy to lose and weak in a dispute. SlipsLedger turns those photos into structured ledger rows with risk flags and a WhatsApp confirmation draft.

## AI core

| Item | Value |
|------|--------|
| Model | `gemma-4-26b-a4b-it` |
| API | Gemini API (`google-genai`) |
| Env var | `GEMINI_API_KEY` |

Payment types: `rent`, `utility`, `security`, `compound_cleaner`, `service_charge`, `other`.

## How to run locally

```powershell
cd C:\Users\LENOVO\Documents\week2-mlh-hacktoberfest
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edit .env and set GEMINI_API_KEY=your_key_from_Google_AI_Studio
streamlit run app.py
```

Open the URL Streamlit prints (usually `http://localhost:8501`).

**Emmanuel:** you must set `GEMINI_API_KEY` in `.env` (or the shell). This repo never invents or commits a key. Get one from [Google AI Studio](https://aistudio.google.com/apikey).

Test with your own real slip photos. There is no mock/stub extraction path and no seeded demo ledger — if the key is missing, the app shows an error instead of fake JSON.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Gemini API key used to call Gemma 4 |

See `.env.example`.

## Features

1. Upload a slip image
2. Call Gemma 4 to classify + extract fields
3. Show payment type, amount/date/parties, risk flags, WhatsApp draft
4. Save to SQLite (`data/slips.db`)
5. List / filter the ledger
6. Export CSV

## Deploy on DigitalOcean App Platform

1. Redeem your Hack Day DigitalOcean credit.
2. Create an App from this GitHub repo (`emarc99/week2-mlh-hacktoberfest`).
3. Use the included `Dockerfile` (Streamlit binds to `$PORT`).
4. Add secret `GEMINI_API_KEY` with your Gemini key.
5. Deploy and paste the live URL into the Ibadan OrganizerHQ form.

## Project layout

```
app.py                 # Streamlit UI
src/gemma_client.py    # Gemma 4 multimodal client
src/prompts.py         # Classification / extraction prompts
src/db.py              # SQLite ledger + CSV export
Dockerfile             # App Platform container
data/                  # slips.db created at runtime (gitignored)
```

## License

MIT — see [LICENSE](LICENSE).
