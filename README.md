# AI Business Analytics Assistant — Starter Project

Upload a CSV, ask questions in plain English, get back tables, numbers, and charts.

## What's inside
```
ai_business_analyst/
├── app.py            # Streamlit UI (chat interface, file upload)
├── core.py           # The engine: profiling, prompt building, LLM call, safe execution
├── requirements.txt
├── .env.example
└── README.md
```

## 1. Setup (run these on your own machine)

```bash
# 1. Create the project folder and move these files into it
mkdir ai_business_analyst && cd ai_business_analyst
# (copy app.py, core.py, requirements.txt, .env.example here)

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your API key
cp .env.example .env
# edit .env and paste your real ANTHROPIC_API_KEY
```

Get a key from https://console.anthropic.com/ (Anthropic API, separate from a claude.ai subscription).

## 2. Run it

```bash
streamlit run app.py
```

This opens a browser tab. Upload any CSV from the sidebar, then ask things like:
- "What are the top 5 products by revenue?"
- "Show me monthly sales trend as a line chart"
- "Which region has the highest average order value?"

## 3. How it works (the core loop)

1. **Profile the CSV** — `profile_dataframe()` builds a short text summary (columns, dtypes, sample rows, stats) instead of sending the whole file to the LLM.
2. **Ask Claude to write code** — the profile + your question go into a strict system prompt that tells the model to write pandas/plotly code into `result` and (optionally) `fig`.
3. **Run it safely** — `safe_execute()` runs that code with a restricted set of builtins and a blocklist for dangerous tokens (file access, subprocess, network, etc).
4. **Auto-retry on error** — if the generated code throws an exception, the error is sent back to the model once, asking it to fix its own code.
5. **Render** — tables via `st.dataframe`, scalars via `st.write`, charts via `st.plotly_chart`.

## 4. Known limitations (be upfront with clients about these)

- The sandbox is a **blocklist + restricted builtins**, which is good enough for a demo/trusted-user MVP, but **not** airtight isolation. Don't expose this directly to untrusted public users without hardening (see below).
- Large CSVs (100k+ rows) will work but cost more tokens per profile/error-retry cycle — consider sampling or pre-aggregating for very large files.
- Currently single-file, single-session (no persistent chat history across restarts).

## 5. Hardening for a real client deployment (do before charging money)

- Run `safe_execute()` in a **separate subprocess with a timeout**, or better, inside a locked-down Docker container with no network access.
- Add row/column limits and a max file size on upload.
- Add authentication if this will be hosted (Streamlit doesn't have built-in auth).
- Log every generated-code execution for auditing.
- Consider caching profiles/answers to cut API costs on repeated questions.

## 6. Natural next features (roadmap)

- [ ] Multi-CSV upload + joins
- [ ] Auto-generated narrative insights (not just numbers)
- [ ] Export conversation + charts to a PDF/PPT report
- [ ] Excel (.xlsx) file support
- [ ] Dockerfile + one-click deploy (Render/Railway)
- [ ] White-label branding for client delivery
