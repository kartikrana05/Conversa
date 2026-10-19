"""Rule-based reply classifier.

How a reply is scored:
1. Normalise the text (lowercase, curly quotes, contractions like "don't" -> "do not").
2. Split it into clauses on punctuation and contrast words ("but", "however", ...).
   Text after "but"/"however" usually carries the real intent, so it counts more.
3. Match whole-word phrases, longest first, so "not interested" is one negative
   signal rather than "not" + a positive "interested".
4. A positive phrase preceded by a negator ("not", "never", ...) in the same clause
   counts as negative ("not really interested", "never asked for a demo").
5. Opt-out requests ("unsubscribe", "stop emailing") always win: they must be honoured.
6. Otherwise the strongest of positive / negative / neutral wins. Deferrals
   ("maybe", "next quarter", "circle back") push towards neutral. No clear signal,
   or a near-tie between conflicting signals, gives neutral.

score_reply() returns the label plus the scores behind it; classify_reply() returns
just the label.
"""

import re
from dataclasses import dataclass

POSITIVE = "positive"
NEGATIVE = "negative"
NEUTRAL = "neutral"

OPT_OUT = "opt_out"

OPT_OUT_PHRASES = [
    "unsubscribe",
    "opt out",
    "stop emailing",
    "stop contacting",
    "stop messaging",
    "stop calling",
    "remove me",
    "take me off",
    "do not contact",
    "do not email",
    "do not message",
    "do not call",
    "leave me alone",
]

NEGATIVE_PHRASES = {
    "not interested": 3,
    "uninterested": 3,
    "disinterested": 3,
    "no thanks": 3,
    "no thank you": 3,
    "not for us": 3,
    "not a fit": 3,
    "not a good fit": 3,
    "not looking": 2,
    "not relevant": 2,
    "no need": 2,
    "not needed": 2,
    "not now": 2,
    "not right now": 2,
    "not at the moment": 2,
    "not yet": 2,
    "not interested right now": 3,
    "not planning": 2,
    "not planning to": 2,
    "not planning on": 2,
    "not planning for": 2,

    "no budget": 2,
    "already have": 2,
    "already using": 2,
    "already use": 2,
    "waste of time": 3,
    "pass on this": 2,
}

POSITIVE_PHRASES = {
    "interested": 2,
    "interesting": 1,
    "demo": 2,
    "schedule a demo": 3,
    "book a demo": 3,
    "book a call": 3,
    "schedule a call": 3,
    "set up a call": 3,
    "hop on a call": 3,
    "tell me more": 2,
    "send me details": 2,
    "send more details": 2,
    "send me more": 2,
    "more information": 1,
    "more info": 1,
    "sounds good": 2,
    "sounds great": 2,
    "let us talk": 2,
    "let us chat": 2,
    "happy to chat": 2,
    "love to": 2,
    "would like to": 1,
    "sign me up": 3,
    "count me in": 3,
    "pricing": 1,
    "how much": 1,
    "curious": 1,
    "keen": 1,
    "yes": 1,
    "sure": 1,
    # Listed so their "no" isn't treated as negating what follows
    "no problem": 1,
    "no worries": 1,
}

NEUTRAL_PHRASES = {
    "maybe": 2,
    "perhaps": 2,
    "not sure": 2,
    "not now": 2,
    "not right now": 2,
    "not at the moment": 2,
    "not yet": 2,
    "later": 2,
    "next week": 2,
    "next month": 2,
    "next quarter": 2,
    "next year": 2,
    "circle back": 2,
    "follow up": 2,
    "reach out": 2,
    "get back to you": 2,
    "think about it": 2,
    "check with": 2,
    "busy": 2,
    "out of office": 3,
    "on vacation": 3,
    "on leave": 3,
}

NEGATORS = {
    "not", "no", "never", "none", "nobody", "nothing",
    "neither", "nor", "without", "hardly", "barely",
}
NEGATION_WINDOW = 4  # how many words before a phrase a negator can be

# Text after these words usually carries the real intent ("Looks good, but not for us")
STRONG_CONTRAST = {"but", "however"}
WEAK_CONTRAST = {"although", "though"}
AFTER_CONTRAST_WEIGHT = 1.5

# The winner must beat the runner-up by at least this much, otherwise it's ambiguous
MIN_MARGIN = 1.0

CONTRACTIONS = [
    (r"\bcan't\b", "can not"),
    (r"\bwon't\b", "will not"),
    (r"\bshan't\b", "shall not"),
    (r"\blet's\b", "let us"),
    (r"n't\b", " not"),
    (r"'re\b", " are"),
    (r"'m\b", " am"),
    (r"'ll\b", " will"),
    (r"'ve\b", " have"),
    (r"'d\b", " would"),
]


def _build_lexicon() -> list[tuple[list[str], str, float]]:
    entries = [(p, OPT_OUT, 0.0) for p in OPT_OUT_PHRASES]
    entries += [(p, NEGATIVE, w) for p, w in NEGATIVE_PHRASES.items()]
    entries += [(p, POSITIVE, w) for p, w in POSITIVE_PHRASES.items()]
    entries += [(p, NEUTRAL, w) for p, w in NEUTRAL_PHRASES.items()]
    lexicon = [(phrase.split(), label, weight) for phrase, label, weight in entries]
    # Longest phrases first, so "not interested" is matched before "interested"
    return sorted(lexicon, key=lambda entry: len(entry[0]), reverse=True)


LEXICON = _build_lexicon()


def _normalise(text: str) -> str:
    text = text.lower().replace("’", "'").replace("‘", "'")
    for pattern, replacement in CONTRACTIONS:
        text = re.sub(pattern, replacement, text)
    return text


def _clauses(text: str) -> list[tuple[list[str], float]]:
    """Split into clauses of words, each with a weight based on contrast words."""
    clauses = []
    weight = 1.0
    for chunk in re.split(r"[.!?;,\n]+", text):
        words: list[str] = []
        for word in re.findall(r"[a-z0-9]+", chunk):
            if word in STRONG_CONTRAST or word in WEAK_CONTRAST:
                if words:
                    clauses.append((words, weight))
                words = []
                weight = AFTER_CONTRAST_WEIGHT if word in STRONG_CONTRAST else 1.0
            else:
                words.append(word)
        if words:
            clauses.append((words, weight))
    return clauses


def _match_phrases(words: list[str]) -> list[tuple[str, float, bool]]:
    """Return (label, weight, negated) for each phrase found, without overlaps."""
    used = [False] * len(words)
    matches = []
    for phrase, label, weight in LEXICON:
        size = len(phrase)
        for start in range(len(words) - size + 1):
            end = start + size
            if words[start:end] == phrase and not any(used[start:end]):
                used[start:end] = [True] * size
                matches.append((start, label, weight))
    # Words inside a matched phrase (e.g. the "no" in "no problem") are not negators
    return [
        (label, weight, _is_negated(words, used, start))
        for start, label, weight in matches
    ]


def _is_negated(words: list[str], used: list[bool], start: int) -> bool:
    window = range(max(0, start - NEGATION_WINDOW), start)
    return any(words[i] in NEGATORS and not used[i] for i in window)


@dataclass(frozen=True)
class ClassificationResult:
    sentiment: str
    positive_score: float
    negative_score: float
    neutral_score: float
    # Winning score minus the runner-up: how clear-cut the reply is.
    # Use it to rank replies within a sentiment (higher = act on it first).
    score_margin: float
    # True when the reply asked to unsubscribe / not be contacted
    opt_out: bool


def score_reply(reply_text: str) -> ClassificationResult:
    scores = {POSITIVE: 0.0, NEGATIVE: 0.0, NEUTRAL: 0.0}
    opt_out = False

    for words, clause_weight in _clauses(_normalise(reply_text)):
        for label, weight, negated in _match_phrases(words):
            if label == OPT_OUT:
                if not negated:
                    opt_out = True
            elif label == POSITIVE and negated:
                # "not interested", "never wanted a demo"
                scores[NEGATIVE] += weight * clause_weight
            elif negated:
                # A negated negative or deferral ("never said no thanks") is too
                # unclear to count either way
                continue
            else:
                scores[label] += weight * clause_weight

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    (top_label, top_score), (_, second_score) = ranked[0], ranked[1]
    margin = top_score - second_score

    if opt_out:
        # Opt-outs must be honoured, whatever else the reply says
        sentiment = NEGATIVE
    elif top_score == 0 or margin < MIN_MARGIN:
        sentiment = NEUTRAL
    else:
        sentiment = top_label

    return ClassificationResult(
        sentiment=sentiment,
        positive_score=scores[POSITIVE],
        negative_score=scores[NEGATIVE],
        neutral_score=scores[NEUTRAL],
        score_margin=margin,
        opt_out=opt_out,
    )


def classify_reply(reply_text: str) -> str:
    return score_reply(reply_text).sentiment
