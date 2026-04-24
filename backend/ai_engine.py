import asyncio
import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

DEFAULT_INSTANT_ACTION = "Critical vitals detected. Start emergency assessment and monitor airway, breathing, and circulation."
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


async def generate_instant_action(vitals: dict[str, Any]) -> str:
    """Return a one-sentence emergency instruction for critical states.

    Uses Groq when configured, and falls back to a safe default message on failures.
    """
    status = str(vitals.get("status", ""))
    if status != "Critical":
        return ""

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return _default_action_from_vitals(vitals)

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_generate_via_groq_sync, api_key, vitals),
            timeout=1.2,
        )
    except Exception:
        return _default_action_from_vitals(vitals)


def _generate_via_groq_sync(api_key: str, vitals: dict[str, Any]) -> str:
    from groq import Groq

    client = Groq(api_key=api_key)

    hr = vitals.get("hr")
    spo2 = vitals.get("spo2")
    movement = vitals.get("movement")

    prompt = (
        "You are an emergency triage assistant. Return exactly one short sentence. "
        "No bullets, no numbering, no extra explanation. "
        f"Vitals: HR={hr}, SpO2={spo2}, Movement={movement}, Status=Critical."
    )

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "Provide immediate, practical, medically conservative actions for first response. "
                    "Keep output under 20 words and exactly one sentence."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=40,
        temperature=0.1,
    )

    content = completion.choices[0].message.content if completion.choices else ""
    clean = (content or "").strip()
    return clean if clean else _default_action_from_vitals(vitals)


def generate_detailed_steps(vitals: dict[str, Any]) -> list[str]:
    """Placeholder for Gemini + RAG pipeline returning three concise steps."""
    status = str(vitals.get("status", ""))
    hr = int(vitals.get("hr", 0) or 0)
    spo2 = int(vitals.get("spo2", 0) or 0)

    if status == "Critical" and spo2 < 90:
        return [
            "Check airway and ensure it is clear.",
            "Sit patient upright and monitor breathing with oxygen saturation.",
            "Prepare emergency escalation and CPR readiness if responsiveness drops.",
        ]

    if status == "Critical" and hr < 50:
        return [
            "Check responsiveness and open airway immediately.",
            "Monitor pulse and breathing continuously for deterioration.",
            "Prepare for CPR and emergency transfer if pulse becomes absent.",
        ]

    if status == "Warning" or hr < 60 or spo2 < 94:
        return [
            "Recheck airway and patient positioning.",
            "Track heart rate and oxygen trend every minute.",
            "Prepare escalation plan if values move toward critical range.",
        ]

    return [
        "Continue routine airway and breathing checks.",
        "Monitor pulse and oxygen levels at regular intervals.",
        "Keep emergency kit ready and reassess if symptoms change.",
    ]


def _default_action_from_vitals(vitals: dict[str, Any]) -> str:
    spo2 = int(vitals.get("spo2", 0) or 0)
    hr = int(vitals.get("hr", 0) or 0)

    if spo2 < 90:
        return "Critical SpO2 detected. Sit patient upright and monitor breathing closely."
    if hr < 50:
        return "Critical heart rate detected. Check pulse immediately and prepare emergency response."

    return DEFAULT_INSTANT_ACTION
