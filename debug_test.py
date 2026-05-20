import json
import asyncio
import httpx
from pathlib import Path

# Load account
with open(r"D:\红线工作区\epos\sub2api\accounts.json", 'r', encoding='utf-8') as f:
    data = json.load(f)

account = data["accounts"][0]
access_token = account["credentials"]["access_token"]
account_id = account["credentials"].get("chatgpt_account_id", "")

print(f"Account: {account['name']}")

# Try different payload formats

# Format 1: input + instructions + store
payload = {
    "model": "gpt-5.4",
    "input": [
        {"role": "user", "content": [{"type": "input_text", "text": "Say hello in one word"}]}
    ],
    "instructions": "You are a helpful assistant.",
    "store": False,
    "stream": True,
}

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json",
    "Accept": "text/event-stream",
    "ChatGPT-Account-ID": account_id,
}

async def test():
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://chatgpt.com/backend-api/codex/responses",
                json=payload,
                headers=headers,
            )
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                text = response.text
                print(f"Response length: {len(text)}")
                print(f"First 500 chars:\n{text[:500]}")
            else:
                print(f"Error: {response.text[:500]}")
    except Exception as e:
        print(f"Exception: {e}")

asyncio.run(test())
