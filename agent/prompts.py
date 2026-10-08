from config import Settings

FALLBACK_SPOKEN_MESSAGE = (
    "Please call back later, I'll pass on your message."
)

GREETING = (
    "Hi, this is {owner}'s AI assistant. How can I help? "
    "I'm an AI, and this call may be transcribed."
)


def build_instructions(settings: Settings) -> str:
    owner = settings.owner_name
    return f"""You are {owner}'s AI phone receptionist. You answer calls.

