
def classify_reply(reply_text: str) -> str:
    text = reply_text.lower().strip()

    negative_keywords = [
        "not interested",
        "no thanks",
        "unsubscribe",
        "stop emailing",
        "don't contact me",
        "not looking",
    ]

    positive_keywords = [
        "interested",
        "schedule a demo",
        "book a call",
        "tell me more",
        "send me details",
    ]

    # Check negative phrases first
    for phrase in negative_keywords:
        if phrase in text:
            return "negative"

    # Check positive phrases
    for phrase in positive_keywords:
        if phrase in text:
            return "positive"

    # Temporary fallback for the two-label MVP
    return "negative"
