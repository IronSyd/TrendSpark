from __future__ import annotations
from datetime import datetime
from typing import Any, Sequence, cast
import logging
import json
from tenacity import retry, stop_after_attempt, wait_exponential

from openai import OpenAI

from .config import settings
from .db import session_scope
from .growth import get_growth_state, GrowthState
from .models import Idea, BrandProfile, Post
from .utils import today_str
from .feedback import adaptive_reply_tones
from .metrics import record_openai_usage


log = logging.getLogger(__name__)


def _openai_client() -> OpenAI | None:
    if not settings.openai_api_key:
        log.info("OPENAI_API_KEY not set; generation disabled")
        return None
    return OpenAI(api_key=settings.openai_api_key)


def _brand_profile_text(bp: BrandProfile | None) -> str:
    if not bp:
        return "brand voice: concise, friendly, value-first"
    parts: list[str] = []
    if bp.adjectives:
        parts.append("adjectives: " + ", ".join(bp.adjectives))
    if bp.voice_notes:
        parts.append("notes: " + bp.voice_notes)
    if bp.examples:
        parts.append("examples: " + " | ".join(bp.examples[:3]))
    return "; ".join(parts)


def _brand_markers(state: GrowthState | None, alias: str) -> list[str]:
    markers = {alias.lower(), alias.replace(" ", "").lower(), "xmoney"}
    if state:
        markers.update(value.lower() for value in state.keywords)
        markers.update(handle.lower().lstrip("@") for handle in state.watchlist)
    return [marker for marker in markers if marker]


def _ensure_brand_reference(
    replies: list[dict], state: GrowthState | None, alias: str
) -> None:
    markers = _brand_markers(state, alias)
    variants = [
        f"{alias} / $XMN keeps day-to-day payments predictable.",
        f"{alias} / $XMN has been the steady pick for real-world payments.",
        f"For a no-fuss option, {alias} / $XMN covers the payments side.",
        f"{alias} / $XMN has stayed in the rotation for actual usage.",
    ]
    for reply in replies:
        text = str(reply.get("reply", "")).strip()
        if not text:
            continue
        normalized = text.lower()
        if any(marker in normalized for marker in markers):
            continue
        addition = variants[hash(text) % len(variants)]
        reply["reply"] = f"{text} {addition}".strip()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def craft_replies_for_post(post: Post, tones: Sequence[str]) -> list[dict]:
    client = _openai_client()
    if client is None:
        return []

    tone_sequence = adaptive_reply_tones(tones)
    if not tone_sequence:
        tone_sequence = list(tones)

    try:
        growth_state = get_growth_state()
    except Exception:
        growth_state = None

    brand_alias = (growth_state.name if growth_state else None) or "XMoney"
    profile_keywords = ", ".join(growth_state.keywords[:8]) if growth_state else ""
    profile_watch = ", ".join(growth_state.watchlist[:5]) if growth_state else ""

    with session_scope() as s:
        bp = s.query(BrandProfile).order_by(BrandProfile.updated_at.desc()).first()
    system = (
        f"You are an active {brand_alias} community member and token holder. Every response must:\n"
        "- Start with a clear stance on the post (agree / disagree / add a take / informative / contrarian).\n"
        f"- Connect that stance to {brand_alias} naturally; first-person is fine but avoid repetitive 'I use $XMN' phrasing.\n"
        "- Sound like a peer, not the team; never use plural pronouns (we/our) or corporate voice.\n"
        "- Keep it concise (1-2 sentences, under 240 chars). Add a short follow-up question only if it fits.\n"
        "- Mention XMoney or $XMN once, varied verbs and angles, mirroring the example posts; avoid boilerplate closers.\n"
        "- Include a subtle CTA or insight only when it adds value; avoid hype, hashtags, and promo-code shilling.\n"
        "- Never imply you are staff; you are a community/user voice."
    )
    voice = _brand_profile_text(bp)
    example_block = ""
    if bp and bp.examples:
        samples = [ex.strip() for ex in bp.examples if ex and ex.strip()]
        if samples:
            formatted = "\n".join(f"- {sample}" for sample in samples[:8])
            example_block = (
                "Example replies that capture the desired tone and XMoney/$XMN mention style "
                "(pick the closest topical match):\n"
                f"{formatted}\n\n"
            )
    stance_examples = (
        '- Utility posts: "Utility matters. I stick with XMoney because it already handles my cross-border payouts."\n'
        '- Presale promos: "Presales feel risky; I use XMoney since it is live and keeps fees predictable."\n'
        '- Comparisons: "Competition is good. For my day-to-day, XMoney has been the reliable option."'
    )
    example_block = (
        f"{example_block}"
        "Reply structure: stance on the post + personal XMoney/$XMN note (first-person, no we/our). "
        "Vary phrasing; avoid templated openers.\n"
        f"{stance_examples}\n\n"
    )
    tone_str = ", ".join(tone_sequence)
    user = (
        "Original post:\n"
        f"{post.text}\n\n"
        f"{example_block}"
        "Brand voice guidance:\n"
        f"{voice}\n\n"
        "Reply requirements:\n"
        "- Lead with a stance (agree, disagree, add a take, informative, or contrarian) on the original post.\n"
        f"- Include one mention of {brand_alias} / $XMN, varied language, no repeated 'I use $XMN' phrasing; first-person singular is optional but no plural pronouns.\n"
        "- Mirror the example posts for tone and angles (utility, compliance, rails, merchant readiness); match context.\n"
        "- Add a short CTA/question only if it fits naturally; avoid hype and hashtags.\n"
        "- Keep it peer-to-peer, never imply you're the team.\n"
        f"- Growth profile keywords/priorities: {profile_keywords or 'n/a'}\n"
        f"- Priority watchlist handles or communities: {profile_watch or 'n/a'}\n"
        f"Tones to cover (mix across replies): {tone_str}\n"
        "Return JSON array of objects: {{tone, reply}}."
    )

    schema: dict[str, Any] = {
        "type": "json_schema",
        "json_schema": {
            "name": "reply_suggestions",
            "schema": {
                "type": "object",
                "properties": {
                    "replies": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "tone": {"type": "string"},
                                "reply": {"type": "string"},
                            },
                            "required": ["reply"],
                        },
                    }
                },
                "required": ["replies"],
                "additionalProperties": False,
            },
        },
    }

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.9,
        response_format=cast(Any, schema),
    )
    _record_openai("reply_suggestions", resp)
    content = resp.choices[0].message.content or "{}"

    try:
        parsed = json.loads(content)
        items = parsed.get("replies", []) if isinstance(parsed, dict) else parsed
        data = items if isinstance(items, list) else []
        results: list[dict] = []
        for item in data:
            t = str(item.get("tone", ""))
            r = str(item.get("reply", ""))
            if r:
                results.append({"tone": t, "reply": r})
        if results:
            _ensure_brand_reference(results, growth_state, brand_alias)
        return results
    except Exception:
        snippet = content[:200].replace("\n", " ")
        log.exception(
            "Failed to parse reply suggestions from OpenAI response (content preview: %s)",
            snippet,
        )
        return []


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def generate_daily_ideas(growth_state: GrowthState | None) -> list[str]:
    client = _openai_client()
    ideas: list[str] = []
    if client is not None:
        with session_scope() as s:
            bp = s.query(BrandProfile).order_by(BrandProfile.updated_at.desc()).first()
        system = (
            "You write 5 concise, high-signal tweets tailored to the user's brand voice. "
            "Each is self-contained, practical, and hooks readers in the first line."
        )
        voice = _brand_profile_text(bp)
        niche_focus = (
            (growth_state.niche or "").strip()
            if growth_state and growth_state.niche
            else "fintech innovation"
        )
        keywords = (
            ", ".join(growth_state.keywords[:8])
            if growth_state and growth_state.keywords
            else "crypto payments, onchain finance, AI fintech copilots"
        )
        watchlist = (
            ", ".join(growth_state.watchlist[:5])
            if growth_state and growth_state.watchlist
            else "xMoney community, Web3 operators"
        )
        user = (
            "Generate exactly 5 net-new tweet ideas as a JSON array of strings."
            "\nEach idea must:"
            "\n- Lead with a bold hook or unexpected insight."
            "\n- Stay aligned with the niche focus and keywords."
            "\n- Offer a practical takeaway, framework, or question that sparks replies."
            "\n- Avoid referencing specific tweets or news headlines; think thematic."
            f"\n\nBrand voice guidance: {voice}"
            f"\nNiche focus: {niche_focus}"
            f"\nPriority keywords/themes: {keywords}"
            f"\nCommunities/accounts to nod to if relevant: {watchlist}"
            "\nReturn JSON array of 5 concise tweet ideas, each under 280 characters."
        )

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.8,
        )
        _record_openai("daily_ideas", resp)
        content = resp.choices[0].message.content or "[]"

        try:
            arr = _extract_idea_array(content)
            ideas = arr[:5]
        except Exception:
            log.exception("Failed to parse OpenAI daily ideas payload")
            ideas = []

    if not ideas:
        raise RuntimeError("OpenAI daily ideas generation returned no content")
    return ideas


def _extract_idea_array(raw: str) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []
    if text.startswith("```"):
        parts = text.split("```")
        for part in parts:
            candidate = part.strip()
            if candidate:
                text = candidate
                break
    if text.lower().startswith("json"):
        text = text.split("\n", 1)[-1]
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    data = json.loads(text)
    if isinstance(data, list):
        return [str(item) for item in data]
    if isinstance(data, dict):
        arr = data.get("ideas")
        if isinstance(arr, list):
            return [str(item) for item in arr]
    return []


def ensure_today_ideas(growth_profile_id: int | None = None) -> list[str]:
    day = today_str()
    try:
        growth_state = get_growth_state(growth_profile_id)
    except ValueError:
        log.warning(
            "Growth profile %s not found; falling back to default", growth_profile_id
        )
        growth_state = get_growth_state()
    with session_scope() as s:
        existing = s.query(Idea).filter(Idea.created_day == day).first()
        if existing:
            return [str(x) for x in (existing.ideas or [])]

    ideas = generate_daily_ideas(growth_state)

    with session_scope() as s:
        row = Idea(created_day=day, ideas=ideas, generated_at=datetime.utcnow())
        s.add(row)
    return ideas


def _record_openai(kind: str, response) -> None:
    usage = getattr(response, "usage", None)
    total_tokens = None
    if usage is not None:
        total_tokens = getattr(usage, "total_tokens", None)
        if total_tokens is None and isinstance(usage, dict):
            total_tokens = usage.get("total_tokens")
    record_openai_usage(kind, total_tokens)
