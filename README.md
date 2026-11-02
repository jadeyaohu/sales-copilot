# AI Sales Copilot

An AI agent that helps SDRs decide **who to contact first** and **what to say**, with a human approving every message.

## The problem
At my startup, the hardest part of outbound wasn't making calls; it was knowing which prospects were ready to talk. Reps waste hours on accounts that aren't in-market.

## How it works
For each lead, the agent runs three steps:

1. **Research** – reads the company's public website.
2. **Score** – rates fit against an ideal customer profile (0–100), flags a "why now" signal (hiring, funding, launch, expansion) and the likely pain point, with a confidence level.
3. **Draft** – writes a short email (< 75 words) and a 30-second call opener.

Then the **rep reviews, edits, approves or skips** each draft. Nothing is sent automatically. Results export to CSV, and a summary shows leads processed, approved, skipped and average fit.

## Design choices
- **Human in the loop:** AI drafts, people decide. This protects the brand and catches mistakes.
- **No invented facts:** prompts tell the model to use only the data provided and to lower confidence when information is missing.
- **Public data only:** no scraping of LinkedIn or private sources.
- **Mock mode:** runs without an API key for demos.

## Run it
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key   # optional; without it the app uses mock mode
streamlit run app.py
```
Pick a **Demo scenario** (sales intelligence or AI data analytics), then upload a CSV with columns `company, name, title, website, notes`, or click **Use sample leads** (fictional companies).

## Deploy (Streamlit Community Cloud, free)
1. Push this folder to a public GitHub repo (the `.gitignore` keeps secrets out).
2. Go to share.streamlit.io → **Create app** → pick the repo, branch `main`, file `app.py` → **Deploy**.
3. Do **not** add your API key as a secret on a public app: visitors would spend your credits. The public link runs in mock mode; paste your key into the sidebar only when you demo live (it is used for that session only and never shown back).

## Stack
Python · Streamlit · Claude API · pandas · requests/BeautifulSoup

## Next steps
- Connect to HubSpot or Salesforce
- Add buying-intent signals from job postings and news
- Track which drafts get replies and feed that back into scoring
