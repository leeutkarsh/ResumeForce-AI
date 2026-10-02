import json
import os
import time

from dotenv import load_dotenv
from ollama import Client, ResponseError

load_dotenv(".env")

MODEL = "gemma4:31b"

SYSTEM_PROMPT = (
    "You are ResumeForce AI. "
    "Always return valid JSON only. "
    "Never return markdown or text outside JSON."
)

API_KEY = os.getenv("OLLAMA_API_KEY")

if not API_KEY:
    raise RuntimeError("OLLAMA_API_KEY is missing. Add it to your .env file.")

client = Client(
    host="https://ollama.com",
    headers={"Authorization": f"Bearer {API_KEY}"},
)


def parse(content: str, done_reason=None) -> dict:
    start, end = content.find("{"), content.rfind("}")
    text = content[start:end + 1] if start != -1 and end != -1 else content

    try:
        result = json.loads(text)
    except json.JSONDecodeError as error:
        if done_reason == "length":
            raise ValueError("The model's output was cut off.") from error
        raise ValueError(f"Model returned invalid JSON: {content[:200]!r}") from error

    if not isinstance(result, dict):
        raise ValueError("LLM response must be a JSON object.")

    return result


def llm(prompt: str) -> dict:
    for attempt in range(2):
        try:
            response = client.chat(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                format="json",
                options={"temperature": 0},
            )
        except (ResponseError, ConnectionError) as error:
            if attempt == 0:
                time.sleep(2)
                continue
            raise RuntimeError(f"ResumeForce LLM failed: {error}") from error

        return parse(response.message.content, response.done_reason)