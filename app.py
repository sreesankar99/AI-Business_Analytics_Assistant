"""
app.py
Streamlit front-end for the AI Business Analytics Assistant.

Run with:
    streamlit run app.py
"""

import os
import hashlib
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from io import BytesIO

from core import profile_dataframe, ask

load_dotenv()

def create_answer_summary(result, max_rows=5):
    """
    Convert the result into a short summary
    that can be stored in conversation memory.
    """

    if result is None:
        return "No result was returned."

    # DataFrame result
    if isinstance(result, pd.DataFrame):
        if result.empty:
            return "The result is an empty table."

        preview = result.head(max_rows).to_string(index=False)

        return (
            f"Returned a table with {len(result)} rows "
            f"and {len(result.columns)} columns.\n"
            f"Columns: {', '.join(map(str, result.columns))}\n"
            f"Preview of the first {min(max_rows, len(result))} rows:\n"
            f"{preview}"
        )

    # Series result
    if isinstance(result, pd.Series):
        return (
            f"Returned a Series with {len(result)} values.\n"
            f"Preview:\n{result.head(max_rows).to_string()}"
        )

    # Single number, string, or other simple result
    return str(result)[:2000]

st.set_page_config(
    page_title="AI Business Analytics Assistant",
    layout="wide"
)

st.title("📊 AI Business Analytics Assistant")
st.caption("Upload a CSV, ask questions in plain English, get answers and charts.")


# ---------------------------------------------------------------------------
# API key handling
# ---------------------------------------------------------------------------

api_key = os.getenv("OPENROUTER_API_KEY")

if not api_key:
    api_key = st.sidebar.text_input(
        "OpenRouter API Key",
        type="password"
    )

if not api_key:
    st.warning(
        "Enter your OpenRouter API key in the sidebar "
        "(or set it in a .env file) to continue."
    )

    st.stop()


# OpenRouter uses an OpenAI-compatible API
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key
)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "history" not in st.session_state:
    st.session_state.history = []

if "df" not in st.session_state:
    st.session_state.df = None

if "profile" not in st.session_state:
    st.session_state.profile = None

if "file_fingerprint" not in st.session_state:
    st.session_state.file_fingerprint = None

if st.sidebar.button("🧹 Clear Conversation Memory"):
    st.session_state.history = []
    st.rerun()

# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------

uploaded_file = st.sidebar.file_uploader(
    "Upload a CSV or Excel file",
    type=["csv", "xlsx", "xls"]
)
if uploaded_file is not None:

    file_name = uploaded_file.name.lower()
    file_bytes = uploaded_file.getvalue()

    # --------------------------------
    # Read CSV files
    # --------------------------------
    if file_name.endswith(".csv"):

        try:
            df = pd.read_csv(BytesIO(file_bytes), encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(BytesIO(file_bytes), encoding="latin1")

        dataset_id = hashlib.sha256(file_bytes).hexdigest()

    # --------------------------------
    # Read Excel files
    # --------------------------------
    elif file_name.endswith((".xlsx", ".xls")):

        excel_file = pd.ExcelFile(BytesIO(file_bytes))

        sheet_name = st.sidebar.selectbox(
            "Select Excel worksheet",
            excel_file.sheet_names
        )

        df = pd.read_excel(
            excel_file,
            sheet_name=sheet_name
        )

        dataset_id = hashlib.sha256(
            file_bytes + sheet_name.encode("utf-8")
        ).hexdigest()

    # --------------------------------
    # Reset memory if dataset changes
    # --------------------------------
    if st.session_state.file_fingerprint != dataset_id:

        st.session_state.history = []
        st.session_state.df = None
        st.session_state.profile = None

        st.session_state.file_fingerprint = dataset_id

    # --------------------------------
    # Save dataset and profile
    # --------------------------------
    st.session_state.df = df
    st.session_state.profile = profile_dataframe(df)

    st.success("File uploaded successfully!")

# ---------------------------------------------------------------------------
# Show data
# ---------------------------------------------------------------------------

if st.session_state.df is not None:

    with st.expander(
        "Preview data & profile",
        expanded=False
    ):

        st.dataframe(
            st.session_state.df.head(20)
        )

        st.text(
            st.session_state.profile
        )

else:

    st.info(
        "Upload a CSV file from the sidebar to get started."
    )

    st.stop()


# ---------------------------------------------------------------------------
# Chat interface
# ---------------------------------------------------------------------------

for turn in st.session_state.history:

    with st.chat_message("user"):
        st.write(turn["question"])

    with st.chat_message("assistant"):

        st.write(
            turn["answer_summary"]
        )

        if turn.get("fig") is not None:

            st.plotly_chart(
                turn["fig"],
                use_container_width=True
            )

        with st.expander(
            "Show generated code"
        ):

            st.code(
                turn["code"],
                language="python"
            )


question = st.chat_input(
    "Ask a question about your data..."
)


if question:

    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):

        with st.spinner("Analyzing..."):

            outcome = ask(
                client=client,
                df=st.session_state.df,
                profile=st.session_state.profile,
                question=question,
                history=st.session_state.history,
            )

        if outcome["error"]:

            st.error(
                f"Couldn't complete the analysis after retrying.\n\n"
                f"{outcome['error']}"
            )

            with st.expander(
                "Show attempted code"
            ):

                st.code(
                    outcome["code"],
                    language="python"
                )

            answer_summary = (
                "Error: could not complete this analysis."
            )

        else:

            result = outcome["result"]
            fig = outcome["fig"]

            if isinstance(
                result,
                (pd.DataFrame, pd.Series)
            ):

                st.dataframe(result)

                answer_summary = (
                    f"Returned a table with shape "
                    f"{getattr(result, 'shape', '')}"
                )

            elif result is not None:

                st.write(result)

                answer_summary = str(result)[:300]

            else:

                answer_summary = (
                    "Generated a chart (see below)."
                )

            if fig is not None:

                st.plotly_chart(
                    fig,
                    use_container_width=True
                )

            with st.expander(
                "Show generated code"
            ):

                st.code(
                    outcome["code"],
                    language="python"
                )


        # Create a useful summary of the result
        answer_summary = create_answer_summary(
            outcome.get("result")
        )

        # Save the question and answer in conversation memory
        st.session_state.history.append({
            "question": question,
            "answer_summary": answer_summary,
            "fig": outcome.get("fig"),
            "code": outcome.get("code", ""),
        })
        