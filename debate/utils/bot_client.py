import anthropic
from django.conf import settings

_BOT_SYSTEM = """\
You are a sharp, well-informed human debate competitor participating in a live structured debate.

Your character: You are knowledgeable, passionate, and articulate. You cite real facts, statistics, \
and examples naturally — the way a human expert would. You argue with conviction, no hedging, \
no disclaimers.

Critical rules:
- Never reveal you are an AI or a language model
- Never use phrases like "As an AI", "I should note", or "It is important to acknowledge"
- Speak in first person directly as yourself
- No labels or prefixes like "PRO:", "Opening:", "My argument:"
- Keep your response under 350 characters"""

_ROUND_INSTRUCTIONS = {
    "OPENING": "Present your strongest opening argument. Lead with your most compelling point and back it with a concrete fact or example.",
    "REBUTTAL": "Directly counter your opponent's last argument. Identify the weakest claim they made and dismantle it with evidence.",
    "CLOSING": "Deliver your final, decisive argument. Summarise why your side wins and leave the judge with one powerful, memorable point.",
}


def _build_prompt(
    *,
    topic: str,
    description: str,
    side: str,
    round_type: str,
    history: list[str],
) -> str:
    side_label = "in FAVOUR of the topic" if side == "PRO" else "AGAINST the topic"
    instruction = _ROUND_INSTRUCTIONS.get(round_type, "Make your best argument.")
    history_text = "\n".join(history) if history else "No previous arguments yet."

    lines = [f"Topic: {topic}"]
    if description:
        lines.append(f"Context: {description}")
    lines += [
        f"Your position: {side} — argue {side_label}",
        f"Round: {round_type} — {instruction}",
        "",
        "Debate so far:",
        history_text,
        "",
        "Write your argument now. Be direct, factual, and persuasive. Under 350 characters.",
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
            max_tokens=200,
            system=[
                {
                    "type": "text",
                    "text": _BOT_SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()[:400]


bot_client = DebateBotClient()
