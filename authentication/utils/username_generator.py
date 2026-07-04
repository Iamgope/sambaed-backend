import secrets

_DEFAULT_ADJECTIVES = [
    "Eloquent", "Bold", "Sharp", "Fierce", "Logical", "Clever", "Candid",
    "Precise", "Astute", "Vivid", "Lucid", "Stoic", "Keen", "Witty", "Calm",
]

_DEFAULT_NOUNS = [
    "Orator", "Debater", "Arguer", "Speaker", "Advocate", "Thinker",
    "Reasoner", "Scholar", "Critic", "Sage", "Voice", "Pundit",
]


def generate_username() -> str:
    from authentication.services import get_username_base_to_generate_usernames

    config = get_username_base_to_generate_usernames()
    adjectives = config.get("adjectives") or _DEFAULT_ADJECTIVES
    debate_nouns = config.get("debate_nouns") or _DEFAULT_NOUNS
    suffix_min = config.get("suffix_min", 1000)
    suffix_max = config.get("suffix_max", 9999)

    adjective = secrets.choice(adjectives)
    noun = secrets.choice(debate_nouns)
    suffix = secrets.randbelow(suffix_max - suffix_min + 1) + suffix_min
    return f"{adjective}{noun}{suffix}"
