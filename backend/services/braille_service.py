import re
import unicodedata
from data.braille_map import BRAILLE_MAP, dots_to_motors

# one token = optional opening quote + core + trailing punctuation, e.g. "Why?"
# core: letters with inner apostrophes/hyphens (don't, well-known), or digits
# with an inner '.' or ',' (3.5, 1,000)
TOKEN = re.compile(r'''(")?([a-zA-Z]+(?:['-][a-zA-Z]+)*|\d+(?:[.,]\d+)*)([.,;:!?"]*)''')
QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})


def normalize(text: str) -> str:
    """Straight quotes and no accents: "Don’t" -> "Don't", "café" -> "cafe"."""
    text = unicodedata.normalize("NFKD", text.translate(QUOTES))
    return "".join(c for c in text if not unicodedata.combining(c))


def split_sentences(text: str) -> list[str]:
    """Split summary text into sentences on '.', '!', '?' and on line breaks."""
    parts = re.split(r"(?<=[.!?])\s+|\s*\n\s*", normalize(text).strip())
    return [p for p in parts if p]


def split_words(sentence: str) -> list[str]:
    """Split a sentence into words/numbers with their punctuation attached,
    one character per Braille cell: 'He said, "Take 2."' ->
    ['He', 'said,', '“Take', '#2.”']. Numbers get the UEB number sign '#';
    a quote before a word opens (“), after it closes (”). Other symbols are dropped."""
    words = []
    for quote, core, tail in TOKEN.findall(normalize(sentence)):
        if core[0].isdigit():
            core = "#" + core
        words.append(("“" if quote else "") + core + tail.replace('"', "”"))
    return words


def char_to_braille(ch: str) -> tuple[list[int], list[bool]]:
    """Convert one character to (active_dots, motor_states).
    Characters not in BRAILLE_MAP return no active dots."""
    dots = BRAILLE_MAP.get(ch.lower(), [])
    motors = dots_to_motors(dots)
    return dots, motors
