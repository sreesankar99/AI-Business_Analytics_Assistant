# AI Business Analytics Assistant

A Streamlit application that lets you upload CSV or Excel data, ask questions in plain English, and receive calculated answers, tables, and interactive Plotly charts.

The application uses the **OpenRouter API** with its `openrouter/free` model router. OpenRouter provides access to available free models through an OpenAI-compatible API, so the project does not require an Anthropic API key.

## Features

- Upload `.csv`, `.xlsx`, and `.xls` files.
- Select a worksheet when uploading an Excel workbook.
- Inspect a data preview and an automatically generated data profile.
- Ask questions in natural language through a chat interface.
- Generate pandas and Plotly code to answer questions.
- Display scalar answers, DataFrames, Series, and interactive charts.
- Keep short conversation memory for follow-up questions.
- Retry once automatically when generated analysis code fails.
- Show generated Python code for transparency and debugging.
- Reset conversation memory when a different dataset is uploaded.

## Project structure

```text
AI-Business_Analytics_Assistant/
├── app.py             # Streamlit interface, uploads, chat, and rendering
├── core.py            # Profiling, prompts, OpenRouter calls, and execution
├── requirements.txt   # Python dependencies
├── .env.example       # Environment-variable template
└── README.md
```

## How the application works

1. **Upload data** – `app.py` reads a CSV or Excel worksheet into a pandas DataFrame.
2. **Create a profile** – `profile_dataframe()` sends the model a compact description containing the shape, columns, data types, null counts, sample rows, and numeric statistics. The complete dataset is not sent to the model.
3. **Generate analysis code** – OpenRouter is asked to produce pandas/NumPy/Plotly code using the existing `df` variable. The requested answer must be stored in `result`; charts are stored in `fig`.
4. **Execute locally** – `safe_execute()` runs the generated code with restricted globals and a blocked-token check.
5. **Retry errors** – If execution fails, the error is sent back to the model once so it can generate corrected code.
6. **Render the result** – Streamlit displays tables, scalar values, and Plotly figures.

## Requirements

- Python 3.10 or newer recommended
- An OpenRouter account and API key
- Internet access while making model requests

The project uses the OpenAI Python SDK only as an API client. Requests are directed to OpenRouter with:

```text
https://openrouter.ai/api/v1
```

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/sreesankar99/AI-Business_Analytics_Assistant.git
cd AI-Business_Analytics_Assistant
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv

# macOS/Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create an OpenRouter API key

Create an account at [OpenRouter](https://openrouter.ai/), create an API key, and copy the key. The application is configured to use the free model router:

```text
openrouter/free
```

Free model availability and rate limits can change on OpenRouter. A free key may still be subject to provider limits or temporary unavailability.

### 5. Configure the environment

Copy the example file and add your key:

```bash
# macOS/Linux
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

Set the value in `.env`:

```dotenv
OPENROUTER_API_KEY=your_openrouter_key_here
```

Never commit `.env` or expose your API key in the browser, source code, screenshots, or logs.

## Run the application

```bash
streamlit run app.py
```

Then upload a dataset from the sidebar and ask questions such as:

- `What are the top 5 products by revenue?`
- `Show monthly sales as a line chart.`
- `Which region has the highest average order value?`
- `How many rows contain missing customer IDs?`

Follow-up questions can refer to the recent conversation, for example: `Show that by region instead.`

## Important security limitation

The generated Python code is executed in the same process as the Streamlit application. The project uses restricted builtins and a blocklist, but this is **not a secure isolation boundary**. It is suitable for a local demo or trusted users only.

Before exposing the application to untrusted users, run code execution in a separate process with a timeout or, preferably, in a locked-down container with:

- No network access
- Read-only or no filesystem access
- CPU, memory, and execution-time limits
- Authentication and authorization
- Detailed execution auditing

Do not treat the current `safe_execute()` implementation as production-grade sandboxing.

## Current limitations

- Free OpenRouter models can have rate limits, queue delays, or changing availability.
- Very large files increase profiling and model-request costs; use sampling or pre-aggregation for large datasets.
- Conversation memory is held only in the current Streamlit session and is lost after restart.
- The model receives a profile and sample rows, not every row in the dataset. Some questions may therefore require a more explicit prompt or local preprocessing.
- Generated-code execution can fail when column names, date formats, or user questions are ambiguous.
- There is no built-in authentication, persistent storage, report export, or multi-user data isolation.

## Recommended next steps

- [ ] Add upload size, row-count, and column-count limits.
- [ ] Move generated-code execution to an isolated subprocess/container.
- [ ] Add authentication and per-user session isolation.
- [ ] Add structured validation for generated code and result types.
- [ ] Add multi-file uploads and joins.
- [ ] Add narrative insights and downloadable PDF/PPT reports.
- [ ] Add caching for profiles and repeated questions.
- [ ] Add tests for profiling, code extraction, unsafe-token detection, and execution errors.

## License

No license has been declared yet. Add a license file before distributing or deploying the project publicly.
