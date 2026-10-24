from dotenv import load_dotenv
import os, json, urllib.request, urllib.error
load_dotenv()

key = os.getenv("GROQ_API_KEY")
model = os.getenv("GROQ_MODEL")
url = "https://api.groq.com/openai/v1/chat/completions"
body = json.dumps({"model": model, "messages": [{"role": "user", "content": "Hello"}]}).encode()

def test(label, extra_headers):
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    headers.update(extra_headers)
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(label, "-> OK", r.status)
    except urllib.error.HTTPError as e:
        print(label, "-> FAILED", e.code, e.read().decode()[:200])
    except Exception as e:
        print(label, "-> ERROR", e)

test("Without User-Agent", {})
test("With User-Agent   ", {"User-Agent": "Mozilla/5.0"})
