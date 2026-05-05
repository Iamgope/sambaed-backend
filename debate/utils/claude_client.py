import json
from typing import Dict

import anthropic
from django.conf import settings

_JUDGE_SYSTEM_PROMPT = """\
You are a strict but fair debate judge. Evaluate 1v1 structured debates objectively.

Score each debater 1-10 on four dimensions:
- Argument Strength (30%): coherence and support for their position
- Rebuttal/Engagement (30%): addressing the opponent's points
- Persuasiveness (25%): moving the needle on the topic
- Clarity (15%): ease of following the argument

Respond ONLY with valid JSON, no extra text:
{
  "winner": "pro" or "con",
  "pro": {
    "argument_score": <1-10>,
    "rebuttal_score": <1-10>,
    "clarity_score": <1-10>,
    "persuasion_score": <1-10>
  },
  "con": {
    "argument_score": <1-10>,
    "rebuttal_score": <1-10>,
    "clarity_score": <1-10>,
    "persuasion_score": <1-10>
  },
  "reasoning": "<2-3 sentence verdict rationale>",
  "strongest_moment": "<exact quote of the single best argument from the debate>",
  "coaching_tip_pro": "<one specific actionable improvement tip for the pro debater>",
  "coaching_tip_con": "<one specific actionable improvement tip for the con debater>"
}"""


class ClaudeJudgeClient:
    """Calls Claude to judge a debate transcript.

    The system prompt is marked for prompt caching — it never changes between
    debates, so repeated judging calls pay only for the transcript tokens.
    """

    def __init__(self) -> None:
        self._client: anthropic.Anthropic | None = None

    def _get_client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._client

    def judge(self, *, transcript: str, judge_config: Dict) -> dict:
        client = self._get_client()
        system_prompt = judge_config.get("system_prompt", _JUDGE_SYSTEM_PROMPT)
        model = judge_client.get("model", "claude-sonnet-4-6")
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    # Cache the system prompt — it is identical for every debate.
                    # First call writes the cache; subsequent calls read it at ~10% cost.
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": f"Evaluate the following debate transcript:\n\n{transcript}",
                }
            ],
        )
        return json.loads(response.content[0].text.strip())


judge_client = ClaudeJudgeClient()
