import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core import config
from app.core.auth import get_current_user
from app.db.models import User

router = APIRouter(prefix="/assistant", tags=["assistant"])


class AssistantRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    context: dict = Field(default_factory=dict)


def _local_answer(question, context):
    profile = context.get("profile") or {}
    warnings = profile.get("warnings") or []
    target = context.get("target") or "not selected"
    details = []
    if target != "not selected":
        details.append(f"current target is {target}")
    if context.get("task"):
        details.append(f"the selected task is {context['task']}")
    if warnings:
        details.append(f"the dataset has {len(warnings)} quality warning(s)")
    state = "; ".join(details) if details else "no dataset context is available yet"
    return (
        f"I cannot reach the AI provider right now, so I cannot reliably answer that request. "
        f"Current workspace context: {state}. Please try again when the AI service is available."
    )


@router.post("")
def ask_assistant(request: AssistantRequest, _user: User = Depends(get_current_user)):
    fallback = _local_answer(request.question, request.context)
    if not config.GROQ_API_KEY:
        return {"answer": fallback, "source": "local"}
    prompt = (
        "You are a general-purpose AI assistant embedded in AutoML Studio. "
        "Answer the user's actual question directly instead of selecting a canned response. "
        "You can answer general conversation and also explain dataset quality, target/features, "
        "preprocessing, models, errors, results, and workflow steps when relevant. "
        "Understand English, Urdu, Roman Urdu, Roman English, and mixed language. "
        "Reply in the user's language and style; if the user writes Roman Urdu, reply in clear Roman Urdu. "
        "Never invent metrics. Dataset context and previous conversation follow:\n"
        f"{json.dumps(request.context, default=str)}\n\nUser question: {request.question}"
    )
    payload = json.dumps({
        "model": config.MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 500,
    }).encode()
    try:
        response_request = Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {config.GROQ_API_KEY}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",  # <-- yehi ek line add hui hai (Cloudflare 1010 fix)
            },
            method="POST",
        )
        with urlopen(response_request, timeout=20) as response:
            body = json.loads(response.read().decode())
        answer = body["choices"][0]["message"]["content"]
        return {"answer": answer, "source": "groq"}
    except HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode()).get("error", {}).get("message", str(exc))
        except (OSError, TypeError, json.JSONDecodeError):
            detail = str(exc)
        return {
            "answer": f"Groq AI request failed ({exc.code}): {detail}",
            "source": "groq_error",
        }
    except (OSError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        return {
            "answer": f"Groq AI request could not be completed: {exc}",
            "source": "groq_error",
        }
