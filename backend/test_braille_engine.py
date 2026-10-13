"""
Phase 3 verification script — run this directly to check every letter a-z
against its known-correct UEB Grade 1 pattern, with no server, dashboard,
or hardware needed.

Run from inside the backend/ folder:
    python test_braille_engine.py
"""

from collections import defaultdict

from data.braille_map import BRAILLE_MAP
from services.braille_service import char_to_braille, split_sentences, split_words

# Known-correct reference patterns (dot numbers 1-6) to check against.
# If any letter fails, the bug is in data/braille_map.py, not here.
EXPECTED = {
    'a': [1],             'b': [1, 2],          'c': [1, 4],
    'd': [1, 4, 5],       'e': [1, 5],          'f': [1, 2, 4],
    'g': [1, 2, 4, 5],    'h': [1, 2, 5],       'i': [2, 4],
    'j': [2, 4, 5],       'k': [1, 3],          'l': [1, 2, 3],
    'm': [1, 3, 4],       'n': [1, 3, 4, 5],    'o': [1, 3, 5],
    'p': [1, 2, 3, 4],    'q': [1, 2, 3, 4, 5], 'r': [1, 2, 3, 5],
    's': [2, 3, 4],       't': [2, 3, 4, 5],    'u': [1, 3, 6],
    'v': [1, 2, 3, 6],    'w': [2, 4, 5, 6],    'x': [1, 3, 4, 6],
    'y': [1, 3, 4, 5, 6], 'z': [1, 3, 5, 6],
}


def cell_diagram(dots: list[int]) -> str:
    """Render a 2x3 ascii braille cell: dots 1/4 top, 2/5 middle, 3/6 bottom."""
    rows = []
    for left, right in [(1, 4), (2, 5), (3, 6)]:
        l = "●" if left in dots else "○"
        r = "●" if right in dots else "○"
        rows.append(f"{l} {r}")
    return "  ".join(rows)  # compact one-line form: "l1 r1  l2 r2  l3 r3"


def main():
    failures = []
    print(f"{'Letter':<8}{'Dots':<18}{'Cell (1 4 / 2 5 / 3 6)':<28}{'Motors (M1..M6)'}")
    print("-" * 80)

    for letter in "abcdefghijklmnopqrstuvwxyz":
        dots, motors = char_to_braille(letter)
        expected = EXPECTED[letter]
        ok = sorted(dots) == sorted(expected)
        if not ok:
            failures.append((letter, dots, expected))

        motor_str = "".join("1" if m else "0" for m in motors)
        status = "" if ok else "  <-- MISMATCH"
        print(f"{letter.upper():<8}{str(dots):<18}{cell_diagram(dots):<28}{motor_str}{status}")

    print("-" * 80)
    if failures:
        print(f"\n{len(failures)} letter(s) FAILED:")
        for letter, got, expected in failures:
            print(f"  '{letter}': got {got}, expected {expected}")
    else:
        print("\nAll 26 letters match the expected UEB Grade 1 patterns.")


# Numbers and punctuation, checked against the ICEB UEB symbol list (iceb.org/symbs.html).
SYMBOLS = [
    ("#", "number sign", [3, 4, 5, 6]),
    *[(d, f"digit {d} (= {l})", EXPECTED[l]) for d, l in zip("1234567890", "abcdefghij")],
    ("'", "apostrophe", [3]),
    (".", "full stop / decimal point", [2, 5, 6]),
    (",", "comma", [2]),
    (";", "semicolon", [2, 3]),
    (":", "colon", [2, 5]),
    ("!", "exclamation mark", [2, 3, 5]),
    ("?", "question mark", [2, 3, 6]),
    ("-", "hyphen", [3, 6]),
    ("\u201c", "opening quote", [2, 3, 6]),
    ("\u201d", "closing quote", [3, 5, 6]),
]

# How text is cut into words; each character of a word is one Braille cell.
SENTENCES = [
    ("Don\u2019t visit the caf\u00e9", ["Don't", "visit", "the", "cafe"]),
    ("Take 2 pills, 3.5 mg or 1,000 IU", ["Take", "#2", "pills,", "#3.5", "mg", "or", "#1,000", "IU"]),
    ("\u2018quoted\u2019 students\u2019", ["quoted", "students"]),
    ('He said, "Why?" Well-known: yes; no!', ["He", "said,", "\u201cWhy?\u201d", "Well-known:", "yes;", "no!"]),
    ("\u201cHi,\u201d she said.", ["\u201cHi,\u201d", "she", "said."]),
]


def check_text():
    failures = []
    print(f"\n{'Symbol':<8}{'Name':<28}{'Dots':<16}{'Cell (1 4 / 2 5 / 3 6)':<26}{'Motors (M1..M6)'}")
    print("-" * 92)
    for ch, name, expected in SYMBOLS:
        dots, motors = char_to_braille(ch)
        ok = dots == expected
        if not ok:
            failures.append((ch, dots, expected))
        motor_str = "".join("1" if m else "0" for m in motors)
        print(f"{ch:<8}{name:<28}{str(dots):<16}{cell_diagram(dots):<26}{motor_str}{'' if ok else '  <-- MISMATCH'}")
    print("-" * 92)

    print("\nText -> words (one Braille cell per character):")
    for text, expected in SENTENCES:
        words = split_words(text)
        ok = words == expected
        if not ok:
            failures.append((text, words, expected))
        print(f"  {text!r:<40} -> {' | '.join(words)}{'' if ok else '  <-- MISMATCH'}")
    lines = split_sentences("Take 3.5 mg\nNow. Go!")
    if lines != ["Take 3.5 mg", "Now.", "Go!"]:
        failures.append(("line break split", lines, None))
    print(f"  {'Take 3.5 mg + line break + Now. Go!':<40} -> sentences: {' | '.join(lines)}")

    # Shared patterns: only the ones UEB itself shares (digits reuse a-j after the
    # number sign; '?' and the opening quote are both 2-3-6). Anything else is a mistake.
    groups = defaultdict(set)
    for ch, dots in BRAILLE_MAP.items():
        groups[tuple(sorted(dots))].add(ch)
    shared = {frozenset(v) for v in groups.values() if len(v) > 1}
    allowed = {frozenset({l, d}) for l, d in zip("abcdefghij", "1234567890")} | {frozenset({"?", "“"})}
    print(f"\nShared patterns: {len(shared)}, all allowed by UEB (digits = a-j after the number sign, ? = “)"
          if shared <= allowed else f"\nShared patterns: {len(shared)}")
    for extra in shared - allowed:
        failures.append(("unexpected shared pattern", sorted(extra), None))

    if failures:
        print(f"\n{len(failures)} check(s) FAILED:")
        for what, got, expected in failures:
            print(f"  {what!r}: got {got}, expected {expected}")
    else:
        print(f"\nAll {len(SYMBOLS)} number/punctuation cells and {len(SENTENCES) + 1} text examples are correct.")


if __name__ == "__main__":
    main()
    check_text()
