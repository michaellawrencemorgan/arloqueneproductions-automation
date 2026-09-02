import os
import json
from datetime import datetime, timezone
from supabase import create_client, Client
from openai import OpenAI

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
XAI_API_KEY = os.environ.get("XAI_API_KEY")

if not all([SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, XAI_API_KEY]):
    raise ValueError("Missing one or more required environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
grok = OpenAI(api_key=XAI_API_KEY, base_url="https://api.x.ai/v1")

def fetch_ticker_updates():
    prompt = (
        "You are an automated news wire aggregator for PrayerMapUSA. "
        "Find and summarize 10 timely, factual prayer alerts, breaking US national/regional news, "
        "and community prayer topics from verified wire services, X/Twitter, and local reporting over the last 8 hours. "
        "Return strictly a raw JSON array of objects with no markdown formatting or backticks, matching this exact structure: "
        '[{"title": "Headline text here", "summary": "Brief 1-2 sentence overview", "source": "AP / X / Local News", "state": "Texas", "slug": "texas"}]'
    )

    response = grok.chat.completions.create(
        model="grok-2-latest",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    raw_text = response.choices[0].message.content.strip()

    # Clean markdown fences if present
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:].strip()

    items = json.loads(raw_text)
    now = datetime.now(timezone.utc).isoformat()

    for item in items:
        item["created_at"] = now
        item["published"] = True

    # Insert directly into prayer_news
    supabase.table("prayer_news").insert(items).execute()
    print(f"Successfully inserted {len(items)} items into prayer_news.")

if __name__ == "__main__":
    fetch_ticker_updates()
