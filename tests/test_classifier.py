
from app.services.classifier import classify_reply


def test_positive_reply():
    assert classify_reply("I'm interested in your product") == "positive"


def test_negative_reply():
    assert classify_reply("No thanks, not interested") == "negative"


def test_case_insensitive():
    assert classify_reply("INTERESTED in a demo") == "positive"


def test_unknown_reply():
    assert classify_reply("Please contact me next quarter") == "negative"
