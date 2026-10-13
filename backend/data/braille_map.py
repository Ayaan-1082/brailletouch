# UEB Grade 1, a-z. Dot numbering:
#   1 4
#   2 5
#   3 6

BRAILLE_MAP = {
    'a': [1],
    'b': [1, 2],
    'c': [1, 4],
    'd': [1, 4, 5],
    'e': [1, 5],
    'f': [1, 2, 4],
    'g': [1, 2, 4, 5],
    'h': [1, 2, 5],
    'i': [2, 4],
    'j': [2, 4, 5],
    'k': [1, 3],
    'l': [1, 2, 3],
    'm': [1, 3, 4],
    'n': [1, 3, 4, 5],
    'o': [1, 3, 5],
    'p': [1, 2, 3, 4],
    'q': [1, 2, 3, 4, 5],
    'r': [1, 2, 3, 5],
    's': [2, 3, 4],
    't': [2, 3, 4, 5],
    'u': [1, 3, 6],
    'v': [1, 2, 3, 6],
    'w': [2, 4, 5, 6],
    'x': [1, 3, 4, 6],
    'y': [1, 3, 4, 5, 6],
    'z': [1, 3, 5, 6],
}

# Numbers (UEB). A number starts with the number sign '#' (dots 3-4-5-6) and
# its digits reuse a-j: 1=a ... 9=i, 0=j.
# Punctuation (UEB, checked against the ICEB symbol list, iceb.org/symbs.html).
# '.' and ',' are also the decimal point and comma inside numbers. The opening
# quote shares 2-3-6 with '?', as in print Braille. Quotes arrive as “ ” from
# braille_service.split_words, which decides direction by position.
BRAILLE_MAP.update({
    '#': [3, 4, 5, 6],
    **{digit: BRAILLE_MAP[letter] for digit, letter in zip("1234567890", "abcdefghij")},
    "'": [3],
    '.': [2, 5, 6],
    ',': [2],
    ';': [2, 3],
    ':': [2, 5],
    '!': [2, 3, 5],
    '?': [2, 3, 6],
    '-': [3, 6],
    '“': [2, 3, 6],   # “ opening double quote
    '”': [3, 5, 6],   # ” closing double quote
})


def dots_to_motors(dots: list[int]) -> list[bool]:
    """Convert a list of active dot numbers (1-6) into 6 motor booleans,
    in physical order: Motor1..Motor6 (dot1..dot6)."""
    return [d in dots for d in range(1, 7)]
