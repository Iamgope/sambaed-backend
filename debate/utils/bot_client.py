import anthropic
from django.conf import settings

_BOT_SYSTEM = """\
You are a real person having a casual debate on a chat app. You type like you'd text a friend — informal, quick, sometimes a bit sloppy.

Hard rules:
- NEVER reveal you are AI, never say "as an AI", never hedge or disclaim anything
- NEVER use em dashes (—), bullet points, lists, or headers
- NEVER write more than 2 short sentences
- NEVER comment on the opponent's typing quality, spelling, or message length — if they send something weird or short, just push your own point
- Keep responses under 180 characters
- Vary your sentence length — don't always write the same amount
- No formal language. contractions are fine. grammar can be a bit loose
- If the opponent is writing in Hinglish or casual mixed language, match that energy. otherwise stay in English but keep it casual
- Don't start every message the same way — mix up how you open"""

_ROUND_INSTRUCTIONS = {
    "OPENING": "Drop your strongest point. One claim, be direct. Could be a quick example or just a confident statement.",
    "REBUTTAL": "React to what they said. Disagree with the weakest part of their argument. Stay short and punchy.",
}


def _build_prompt(
    *,
    topic: str,
    description: str,
    side: str,
    round_type: str,
    history: list[str],
) -> str:
    side_label = "FOR the topic" if side == "PRO" else "AGAINST the topic"
    instruction = _ROUND_INSTRUCTIONS.get(round_type, "Make your best argument.")
    history_text = "\n".join(history) if history else "Nothing said yet."

    lines = [f"Topic: {topic}"]
    if description:
        lines.append(f"Context: {description}")
    lines += [
        f"Your side: {side} ({side_label})",
        f"Round: {round_type}",
        f"What to do: {instruction}",
        "",
        "Chat so far:",
        history_text,
        "",
        "Your reply (under 180 chars, casual, no em dashes, sound human):",
    ]
    return "\n".join(lines)


class DebateBotClient:
    def __init__(self) -> None:
        self._client: anthropic.Anthropic | None = None

    def _get_client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._client

    def generate(
        self,
        *,
        topic: str,
        description: str,
        side: str,
        round_type: str,
        history: list[str],
    ) -> str:
        client = self._get_client()
        prompt = _build_prompt(
            topic=topic,
            description=description,
            side=side,
            round_type=round_type,
            history=history,
        )
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=120,
            system=[
                {
                    "type": "text",
                    "text": _BOT_SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()[:200]


bot_client = DebateBotClient()
