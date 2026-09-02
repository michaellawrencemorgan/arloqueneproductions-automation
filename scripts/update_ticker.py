import os
import json
import re
from datetime import datetime, timezone
from supabase import create_client, Client
from openai import OpenAI

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
XAI_API_KEY = os.environ.get("XAI_API_KEY")

if not all([SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, XAI_API_KEY]):
    raise ValueError("Missing one or more required environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
grok = OpenAI(
    api_key=XAI_API_KEY,
    base_url="https://api.x.ai/v1",
    timeout=180.0,
)

def extract_json(text: str):
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise

def fetch_ticker_updates():
    prompt = (
        "You are an automated news wire aggregator for PrayerMapUSA. "
        "Find and summarize 10 timely, factual prayer alerts, breaking US national/regional news, "
        "and community prayer topics from verified wire services, X/Twitter, and local reporting over the last 8 hours. "
        "Return ONLY a JSON object with this exact shape: "
        '{"items":[{"title":"Headline text here","summary":"Brief 1-2 sentence overview","source":"AP / X / Local News","state":"Texas","slug":"texas"}]}'
    )

    response = grok.chat.completions.create(
        model="grok-4.3",
        messages=[
            {
                "role": "system",
                "content": "You output valid JSON only. No markdown. No preface.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=4096,
        response_format={"type": "json_object"},
        extra_body={"reasoning_effort": "low"},
    )

    message = response.choices[0].message
    raw_text = (message.content or "").strip()
    if not raw_text:
        raw_text = (getattr(message, "reasoning_content", None) or "").strip()

    if not raw_text:
        raise RuntimeError(
            f"Grok returned empty content. finish_reason="
            f"{response.choices[0].finish_reason!r} raw={response.model_dump()}"
        )

    parsed = extract_json(raw_text)
    items = parsed.get("items", parsed) if isinstance(parsed, dict) else parsed
    if not isinstance(items, list) or not items:
        raise RuntimeError(f"Unexpected payload: {parsed!r}")

    now = datetime.now(timezone.utc).isoformat()
    for item in items:
        item["created_at"] = now
        item["published"] = True

    supabase.table("prayer_news").insert(items).execute()
    print(f"Successfully inserted {len(items)} items into prayer_news.")

if __name__ == "__main__":
    fetch_ticker_updates()
