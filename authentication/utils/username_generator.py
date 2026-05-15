import secrets

def generate_username() -> str:
    """Return a debate-themed username like 'EloquentOrator4271'.

    Combinations: ~50 * ~37 * 9000 ≈ 16.6M, making collisions extremely rare.
    """
    from authentication.services import get_username_base_to_generate_usernames

    config = get_username_base_to_generate_usernames()
    adjectives = config.get("adjectives", [])
    debate_nouns = config.get("debate_nouns", [])
    suffix_min = config.get("suffix_min", 1000)
    suffix_max = config.get("suffix_max", 9999)

    adjective = secrets.choice(adjectives)
    noun = secrets.choice(debate_nouns)
    suffix = secrets.randbelow(suffix_max - suffix_min + 1) + suffix_min
    return f"{adjective}{noun}{suffix}"
