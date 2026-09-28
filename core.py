"""
core.py

The "brain" of the AI Business Analytics Assistant.

Pipeline:
  1. profile_dataframe() -> turns a raw CSV into a compact text summary
  2. build_user_message() -> combines profile + chat history + question
  3. generate_code() -> asks an LLM to write pandas/plotly code
  4. safe_execute() -> runs that code in a restricted sandbox
  5. ask() -> orchestrates the above, with one auto-retry on error
"""

import io
import contextlib
import traceback
import re

import pandas as pd
import numpy as np

import plotly.express as px
import plotly.graph_objects as go

from openai import OpenAI


# ---------------------------------------------------------------------------
# OpenRouter model
# ---------------------------------------------------------------------------

MODEL_NAME = "openrouter/free"


# ---------------------------------------------------------------------------
# 1. DATA PROFILING
# ---------------------------------------------------------------------------

def profile_dataframe(
    df: pd.DataFrame,
    max_sample_rows: int = 5
) -> str:

    """
    Build a compact text description of the dataframe
    to send to the LLM.

    We do NOT send the full dataset.
    """

    buf = io.StringIO()

    buf.write(
        f"Shape: {df.shape[0]} rows x "
        f"{df.shape[1]} columns\n\n"
    )

    buf.write(
        "Columns (name: dtype, #nulls, #unique):\n"
    )

    for col in df.columns:

        buf.write(
            f"  - {col}: {df[col].dtype}, "
            f"nulls={df[col].isna().sum()}, "
            f"unique={df[col].nunique()}\n"
        )

    buf.write("\nSample rows:\n")

    buf.write(
        df.head(max_sample_rows).to_string()
    )

    numeric_cols = (
        df.select_dtypes(
            include=np.number
        ).columns.tolist()
    )

    if numeric_cols:

        buf.write(
            "\n\nNumeric summary:\n"
        )

        buf.write(
            df[numeric_cols]
            .describe()
            .to_string()
        )

    return buf.getvalue()


# ---------------------------------------------------------------------------
# 2. PROMPT CONSTRUCTION
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are a data analysis code generator.

You will be given:

- A profile describing a pandas DataFrame called `df`.
- A user question in natural language.
- Optionally, recent conversation history.

Your job is to write Python code that answers the question
using ONLY the `df` variable.

STRICT RULES:

1. Only use pandas (as pd), numpy (as np),
   plotly.express (as px), and
   plotly.graph_objects (as go).

2. No other imports.

3. Never read or write files.

4. Never access the network.

5. Never use exec, eval, os, sys, subprocess,
   socket, requests, or similar functions.

6. Store the final answer in a variable called `result`.

7. `result` can be:
   - scalar
   - pandas Series
   - pandas DataFrame

8. If a chart would help answer the question,
   create a Plotly figure in a variable called `fig`.

9. If no chart is needed, do not create `fig`.

10. Output ONLY a single Python code block.

11. Do not provide explanation outside the code block.

12. Assume `df` already exists in scope.

13. Do not redefine or reload `df`.

You are a professional data analyst.

Your task is to generate Python code to analyze the user's DataFrame.

IMPORTANT RULES:
1. The DataFrame is already available as df.
2. pandas is already available as pd.
3. numpy is already available as np.
4. plotly.express is already available as px.
5. plotly.graph_objects is already available as go.

NEVER use import statements.
NEVER use from ... import statements.
NEVER use exec, eval, open, os, sys, or subprocess.
NEVER access files or the network.

Store the final answer in a variable named result.
If a chart is needed, store it in a variable named fig.

Return only Python code.
Do not include explanations or Markdown code fences.
"""


def build_user_message(
    profile: str,
    question: str,
    history: list[dict]
) -> str:

    history_text = ""

    if history:

        history_text = (
            "Recent conversation:\n"
        )

        for turn in history[-4:]:

            history_text += (
                f"Q: {turn['question']}\n"
                f"A (summary): "
                f"{turn['answer_summary']}\n"
            )

        history_text += "\n"

    return f"""
DataFrame profile:

{profile}

{history_text}

Current question:

{question}

Write the Python code now.
"""


def extract_code(text):
    """Extract Python code from the AI response safely."""

    # Check whether the response is empty
    if text is None:
        raise ValueError("The AI returned an empty response.")

    # Convert the response to a string if necessary
    if not isinstance(text, str):
        text = str(text)

    text = text.strip()

    if not text:
        raise ValueError("The AI returned an empty response.")

    # Extract Python code from a Markdown code block
    match = re.search(
        r"```(?:python)?\s*(.*?)```",
        text,
        re.DOTALL | re.IGNORECASE
    )

    if match:
        return match.group(1).strip()

    # If no code block exists, return the response
    return text


# ---------------------------------------------------------------------------
# 3. LLM CALL
# ---------------------------------------------------------------------------

def generate_code(
    client: OpenAI,
    profile: str,
    question: str,
    history: list[dict],
    error_context: str | None = None
) -> str:

    user_msg = build_user_message(
        profile,
        question,
        history
    )

    if error_context:
        user_msg += (
            "\n\nThe previous code you wrote "
            "raised this error:\n"
            f"{error_context}\n\n"
            "Please fix the code and try again. "
            "Output only the corrected Python code."
        )

    response = client.chat.completions.create(
        model=MODEL_NAME,
        max_tokens=2048,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_msg
            }
        ]
    )

    # Check whether the API returned a choice
    if not response.choices:
        raise RuntimeError(
            "OpenRouter returned no choices. "
            "Please try again."
        )

    choice = response.choices[0]
    message = choice.message

    # Extract the generated content
    text = message.content

    # Check for an empty response
    if not text or not text.strip():
        raise RuntimeError(
            "The AI returned no Python code.\n"
            f"Model: {response.model}\n"
            f"Finish reason: {choice.finish_reason}\n"
            f"Message: {message}"
        )

    return extract_code(text)


# ---------------------------------------------------------------------------
# 4. SAFE(R) EXECUTION SANDBOX
# ---------------------------------------------------------------------------

BLOCKED_TOKENS = [

    "import os",
    "import sys",
    "subprocess",
    "open(",
    "exec(",
    "eval(",
    "__import__",
    "shutil",
    "requests",
    "socket",

]


def looks_unsafe(
    code: str
) -> str | None:

    for token in BLOCKED_TOKENS:

        if token in code:

            return token

    return None


def safe_execute(
    code: str,
    df: pd.DataFrame
):

    """
    Executes generated code with a
    restricted set of globals.

    This is suitable for a demo/MVP,
    not a production security sandbox.
    """

    unsafe_token = looks_unsafe(code)

    if unsafe_token:

        raise ValueError(
            f"Blocked potentially unsafe code "
            f"(found '{unsafe_token}')."
        )

    safe_builtins = {

        "len": len,
        "range": range,
        "sum": sum,
        "min": min,
        "max": max,
        "abs": abs,
        "round": round,
        "sorted": sorted,
        "enumerate": enumerate,
        "list": list,
        "dict": dict,
        "set": set,
        "float": float,
        "int": int,
        "str": str,
        "bool": bool,
        "zip": zip,

    }

    sandbox_globals = {

        "__builtins__": safe_builtins,

        "pd": pd,

        "np": np,

        "px": px,

        "go": go,

        "df": df,

    }

    sandbox_locals = {}

    stdout_capture = io.StringIO()

    with contextlib.redirect_stdout(
        stdout_capture
    ):

        exec(
            code,
            sandbox_globals,
            sandbox_locals
        )

    result = sandbox_locals.get(
        "result",
        None
    )

    fig = sandbox_locals.get(
        "fig",
        None
    )

    return (
        result,
        fig,
        stdout_capture.getvalue()
    )


# ---------------------------------------------------------------------------
# 5. ORCHESTRATION
# ---------------------------------------------------------------------------

def ask(
    client: OpenAI,
    df: pd.DataFrame,
    profile: str,
    question: str,
    history: list[dict],
    max_retries: int = 1
):

    """
    Returns:

    {
        code,
        result,
        fig,
        error,
        stdout
    }
    """

    error_context = None

    last_code = ""

    for attempt in range(
        max_retries + 1
    ):

        code = generate_code(

            client,
            profile,
            question,
            history,
            error_context

        )

        last_code = code

        try:

            result, fig, stdout = safe_execute(
                code,
                df
            )

            return {

                "code": code,

                "result": result,

                "fig": fig,

                "error": None,

                "stdout": stdout,

            }

        except Exception as e:

            error_context = (
                f"{type(e).__name__}: {e}\n"
                f"{traceback.format_exc(limit=2)}"
            )

            if attempt == max_retries:

                return {

                    "code": last_code,

                    "result": None,

                    "fig": None,

                    "error": error_context,

                    "stdout": "",

                }

    return None