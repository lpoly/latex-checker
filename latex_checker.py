# latex_checker.py
import re
from bisect import bisect_right

MATH_ENVS = [
    "array",
    "align", "align*",
    "gather", "gather*",
]

ENV_PATTERN = re.compile(
    r'\\begin\{(' + '|'.join(re.escape(e) for e in MATH_ENVS) + r')\}'
    r'.*?'
    r'\\end\{\1\}',
    re.DOTALL
)

MATH_PATTERNS = [
    re.compile(r'\$\$.*?\$\$', re.DOTALL),        # $$ ... $$
    re.compile(r'\\\[.*?\\\]', re.DOTALL),        # \[ ... \]
    re.compile(r'\\\(.*?\\\)', re.DOTALL),        # \( ... \)
    ENV_PATTERN,                                  # math environments
    re.compile(r'\$(?!\$).*?\$', re.DOTALL),      # $ ... $ (single $)
]

SINGLE_LETTER_PATTERN = re.compile(
    r'\b([B-HJ-Zb-hj-z])\b(?=[\s\.,;:!?])'
)


def mask_math_regions(text: str) -> str:
    chars = list(text)
    work_text = text

    for pattern in MATH_PATTERNS:
        for m in pattern.finditer(work_text):
            for i in range(m.start(), m.end()):
                if chars[i] != '\n':
                    chars[i] = ' '
        work_text = ''.join(chars)

    return ''.join(chars)


def get_math_mask(text: str):
    chars = list(text)
    work_text = text
    math_mask = [False] * len(text)

    for pattern in MATH_PATTERNS:
        for m in pattern.finditer(work_text):
            for i in range(m.start(), m.end()):
                math_mask[i] = True
                if chars[i] != '\n':
                    chars[i] = ' '
        work_text = ''.join(chars)

    return math_mask


def build_line_starts(text: str):
    starts = [0]
    for m in re.finditer('\n', text):
        starts.append(m.start() + 1)
    return starts


def index_to_line_col(idx: int, line_starts):
    line_index = bisect_right(line_starts, idx) - 1
    line_start = line_starts[line_index]
    line_no = line_index + 1
    col_no = idx - line_start + 1
    return line_no, col_no


def find_digits_outside_math(text: str):
    masked = mask_math_regions(text)
    line_starts = build_line_starts(text)
    lines = text.splitlines()

    results = []
    for m in re.finditer(r'\d', masked):
        idx = m.start()
        digit = m.group()
        line_no, col_no = index_to_line_col(idx, line_starts)
        line_text = lines[line_no - 1] if 1 <= line_no <= len(lines) else ""
        results.append({
            "kind": "digit",
            "index": idx,
            "line": line_no,
            "col": col_no,
            "char": digit,
            "line_text": line_text,
        })
    return results


def find_single_letters_outside_math(text: str):
    masked = mask_math_regions(text)
    line_starts = build_line_starts(text)
    lines = text.splitlines()

    results = []
    for m in SINGLE_LETTER_PATTERN.finditer(masked):
        idx = m.start(1)
        letter = m.group(1)
        line_no, col_no = index_to_line_col(idx, line_starts)
        line_text = lines[line_no - 1] if 1 <= line_no <= len(lines) else ""
        results.append({
            "kind": "letter",
            "index": idx,
            "line": line_no,
            "col": col_no,
            "char": letter,
            "line_text": line_text,
        })
    return results


def find_commas_colons_inside_math(text: str):
    math_mask = get_math_mask(text)
    line_starts = build_line_starts(text)
    lines = text.splitlines()

    results = []
    for idx, ch in enumerate(text):
        if ch in ',:' and idx < len(math_mask) and math_mask[idx]:
            line_no, col_no = index_to_line_col(idx, line_starts)
            line_text = lines[line_no - 1] if 1 <= line_no <= len(lines) else ""
            results.append({
                "kind": "punct",
                "index": idx,
                "line": line_no,
                "col": col_no,
                "char": ch,
                "line_text": line_text,
            })
    return results

def find_double_backslashes(text: str):
    """
    Find LaTeX line breaks '\\' (two backslashes in a row).

    We return ONE issue per pair,
    but also include 'length': 2 so the highlighter can
    color both characters.
    """
    line_starts = build_line_starts(text)
    lines = text.splitlines()

    results = []
    i = 0
    n = len(text)

    while i < n - 1:
        if text[i] == "\\" and text[i + 1] == "\\":
            line_no, col_no = index_to_line_col(i, line_starts)
            line_text = lines[line_no - 1] if 1 <= line_no <= len(lines) else ""
            results.append({
                "kind": "backslash",
                "index": i,         # index of the FIRST '\'
                "line": line_no,
                "col": col_no,
                "char": "\\\\",     # show two slashes in the issues list
                "line_text": line_text,
                "length": 2,        # <- highlight both characters
            })
            i += 2
        else:
            i += 1

    return results

def find_missing_space_after_punctuation(text: str):
    """
    Find punctuation characters outside math that are not followed by a space
    (or newline / end-of-text / another punctuation / closing quote/paren).

    We treat this as a "spacing" issue.
    """
    masked = mask_math_regions(text)          # hide math so we only check text
    line_starts = build_line_starts(text)
    lines = text.splitlines()

    punctuation = ".,;:!?"                     # chars that should usually be followed by space
    closing_chars = '")\']}>”’'               # we allow these between punctuation and space

    results = []
    n = len(masked)

    for idx, ch in enumerate(masked):
        if ch not in punctuation:
            continue

        j = idx + 1
        if j >= n:
            # punctuation at very end of file is fine
            continue

        # Skip over closing quotes / brackets etc. in the *original* text
        while j < n and text[j] in closing_chars:
            j += 1

        if j >= n:
            # end of text after closers -> fine
            continue

        next_ch = text[j]

        # OK if followed by whitespace or another punctuation
        if next_ch in " \t\n\r" or next_ch in punctuation:
            continue

        # Otherwise: no space after punctuation -> flag it
        line_no, col_no = index_to_line_col(idx, line_starts)
        line_text = lines[line_no - 1] if 1 <= line_no <= len(lines) else ""

        results.append({
            "kind": "spacing",
            "index": idx,
            "line": line_no,
            "col": col_no,
            "char": text[idx],    # the punctuation character
            "line_text": line_text,
        })

    return results


def analyze_text(text: str):
    """Return a flat list of all issues."""
    issues = []
    issues.extend(find_digits_outside_math(text))
    issues.extend(find_single_letters_outside_math(text))
    issues.extend(find_commas_colons_inside_math(text))
    issues.extend(find_missing_space_after_punctuation(text))
    # sort by index so highlighting is deterministic
    issues.sort(key=lambda x: x["index"])
    return issues