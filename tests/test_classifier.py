import pytest

from app.services.classifier import classify_reply


def test_positive_reply():
    assert classify_reply("I'm interested in your product") == "positive"


def test_negative_reply():
    assert classify_reply("No thanks, not interested") == "negative"


def test_case_insensitive():
    assert classify_reply("INTERESTED in a demo") == "positive"


def test_unknown_reply_is_neutral():
    assert classify_reply("Who is this?") == "neutral"


@pytest.mark.parametrize(
    "text",
    [
        "I'm not really interested",
        "We are not at all interested",
        "I never asked for a demo",
        "I don't want to book a call",
        "I’m not interested",  # curly apostrophe
        "We're uninterested",  # must not match "interested" inside the word
    ],
)
def test_negation(text):
    assert classify_reply(text) == "negative"


@pytest.mark.parametrize(
    "text",
    [
        "No problem, send me details",
        "No worries, let's schedule a demo",
    ],
)
def test_no_in_friendly_phrase_is_not_negation(text):
    assert classify_reply(text) == "positive"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Looks interesting, but not for us", "negative"),
        ("Not right now, but tell me more", "positive"),
        ("We already have a tool, but I'd love to see a demo", "positive"),
    ],
)
def test_contrast_favours_what_comes_after_but(text, expected):
    assert classify_reply(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Please contact me next quarter",
        "Maybe, I need to think about it",
        "I'm out of office until Monday",
        "Not interested right now, maybe next quarter",
        "Interested, but not sure",
    ],
)
def test_ambiguous_and_deferred_replies_are_neutral(text):
    assert classify_reply(text) == "neutral"


@pytest.mark.parametrize(
    "text",
    [
        "Yes I'm interested, but please unsubscribe me from the newsletter",
        "Interested in a demo. Also stop emailing my old address",
        "Please don't contact me again",
    ],
)
def test_opt_out_always_wins(text):
    assert classify_reply(text) == "negative"
