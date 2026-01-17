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

def is_punct_protected_in_math(text: str, idx: int, math_mask):
    """
    For a comma/colon at position idx inside math, return True if it looks
    like it's inside braces or parentheses, e.g. \{ a, b \} or (a, b).

    This is a heuristic, not a full parser.
    """
    if not (0 <= idx < len(math_mask) and math_mask[idx]):
        return False

    n = len(text)

    # Look left: skip whitespace
    j = idx - 1
    while j >= 0 and text[j] in " \t\r\n":
        j -= 1

    left_kind = None
    if j >= 0:
        # \{ ... , ... \}
        if text[j] == '{' and j > 0 and text[j - 1] == '\\':
            left_kind = "brace"
        # ( ... , ... )
        elif text[j] == '(':
            left_kind = "paren"
        # [ ... , ... ]
        elif text[j] == '[':
            left_kind = "bracket"

    # Look right: skip whitespace
    k = idx + 1
    while k < n and text[k] in " \t\r\n":
        k += 1

    right_kind = None
    if k < n:
        # \{ ... , ... \}
        if text[k] == '}' and k > 0 and text[k - 1] == '\\':
            right_kind = "brace"
        # ( ... , ... )
        elif text[k] == ')':
            right_kind = "paren"
        # [ ... , ... ]
        elif text[k] == ']':
            right_kind = "bracket"

    return left_kind is not None and left_kind == right_kind

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

def get_math_regions(text: str):
    """
    Return a list of (start, end) index pairs for all math regions in the text,
    using the same patterns as get_math_mask / mask_math_regions.
    """
    chars = list(text)
    work_text = text
    regions = []

    for pattern in MATH_PATTERNS:
        for m in pattern.finditer(work_text):
            regions.append((m.start(), m.end()))
            # mask so later patterns don't "see" inside
            for i in range(m.start(), m.end()):
                if chars[i] != '\n':
                    chars[i] = ' '
        work_text = ''.join(chars)

    return regions


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


# def find_commas_colons_inside_math(text: str):
#     math_mask = get_math_mask(text)
#     line_starts = build_line_starts(text)
#     lines = text.splitlines()

#     results = []
#     for idx, ch in enumerate(text):
#         if ch in ',:' and idx < len(math_mask) and math_mask[idx]:
#             line_no, col_no = index_to_line_col(idx, line_starts)
#             line_text = lines[line_no - 1] if 1 <= line_no <= len(lines) else ""
#             results.append({
#                 "kind": "punct",
#                 "index": idx,
#                 "line": line_no,
#                 "col": col_no,
#                 "char": ch,
#                 "line_text": line_text,
#             })
#     return results

def find_double_backslashes(text: str):
    """
    Find LaTeX line breaks '\\' (two backslashes in a row).
    ...
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
                "index": i,
                "line": line_no,
                "col": col_no,
                "char": "\\\\",
                "line_text": line_text,
                "length": 2,
            })
            i += 2
        else:
            i += 1

    return results


def find_spacing_around_punctuation(text: str):
    """
    Find punctuation characters outside math with bad spacing:
      - a space directly BEFORE the punctuation (e.g. "word ,like this")
      - NO space AFTER the punctuation (e.g. "word,bad spacing")

    We ignore punctuation inside math.
    """
    math_mask = get_math_mask(text)
    line_starts = build_line_starts(text)
    lines = text.splitlines()

    punctuation = ".,;:!?"
    closing_chars = '")\']}>”’'  # chars we can skip AFTER the punctuation

    results = []
    n = len(text)

    for idx, ch in enumerate(text):
        if ch not in punctuation:
            continue

        # Skip punctuation inside math
        if idx < len(math_mask) and math_mask[idx]:
            continue

        # 1) Space BEFORE punctuation?
        has_space_before = (idx > 0 and text[idx - 1] == ' ')

        # 2) Missing space AFTER punctuation?
        j = idx + 1
        # Skip closing quotes/brackets etc.
        while j < n and text[j] in closing_chars:
            j += 1

        missing_space_after = False
        if j < n:
            next_ch = text[j]
            # If the next "real" char is not whitespace, we expect a space
            if next_ch not in " \t\n\r":
                missing_space_after = True
        # If j >= n, punctuation at end-of-text -> OK (no missing space)

        if has_space_before or missing_space_after:
            line_no, col_no = index_to_line_col(idx, line_starts)
            line_text = lines[line_no - 1] if 1 <= line_no <= len(lines) else ""
            results.append({
                "kind": "spacing",
                "index": idx,
                "line": line_no,
                "col": col_no,
                "char": ch,
                "line_text": line_text,
            })

    return results



def find_commas_colons_inside_math(text: str):
    """
    Find commas/colons that are inside math regions, EXCEPT when they appear
    inside groupings like \{ ... \}, (...) or [...].

    We treat any comma/colon that is inside at least one such grouping
    as "protected" and do NOT flag it.
    """
    math_regions = get_math_regions(text)
    line_starts = build_line_starts(text)
    lines = text.splitlines()

    results = []

    for start, end in math_regions:
        stack = []  # track current group context inside this region
        i = start

        while i < end:
            ch = text[i]

            # Detect group openings / closings
            if ch == '{' and i > 0 and text[i - 1] == '\\':
                # \{ ... \}
                stack.append('brace')
            elif ch == '(':
                stack.append('paren')
            elif ch == '[':
                stack.append('bracket')
            elif ch == '}' and i > 0 and text[i - 1] == '\\':
                if stack and stack[-1] == 'brace':
                    stack.pop()
            elif ch == ')':
                if stack and stack[-1] == 'paren':
                    stack.pop()
            elif ch == ']':
                if stack and stack[-1] == 'bracket':
                    stack.pop()

            # Now check commas/colons
            if ch in ',:':
                if not stack:
                    # Only flag if we are *not* inside any grouping
                    line_no, col_no = index_to_line_col(i, line_starts)
                    line_text = lines[line_no - 1] if 1 <= line_no <= len(lines) else ""
                    results.append({
                        "kind": "punct",
                        "index": i,
                        "line": line_no,
                        "col": col_no,
                        "char": ch,
                        "line_text": line_text,
                    })

            i += 1

    return results





def find_spacing_inside_delimiters(text: str):
    """
    Find spaces just inside parentheses or quotes OUTSIDE math, e.g.
      ( example )   -> the spaces after '(' and before ')'
      " example "   -> the spaces after first quote and before last quote
    """
    math_mask = get_math_mask(text)
    line_starts = build_line_starts(text)
    lines = text.splitlines()

    left_delims = '(["“‘'
    right_delims = ')]"”’'

    results = []
    n = len(text)

    for idx, ch in enumerate(text):
        if ch != ' ':
            continue

        # Skip spaces inside math
        if idx < len(math_mask) and math_mask[idx]:
            continue

        bad = False

        # Space immediately AFTER an opening delimiter, e.g. "( " or "\" "
        if idx > 0 and text[idx - 1] in left_delims:
            bad = True

        # Space immediately BEFORE a closing delimiter, e.g. " )" or " \""
        if idx + 1 < n and text[idx + 1] in right_delims:
            bad = True

        if bad:
            line_no, col_no = index_to_line_col(idx, line_starts)
            line_text = lines[line_no - 1] if 1 <= line_no <= len(lines) else ""
            results.append({
                "kind": "spacing",
                "index": idx,
                "line": line_no,
                "col": col_no,
                # Use a visible symbol in the issues list
                "char": "␣",
                "line_text": line_text,
            })

    return results


def analyze_text(text: str):
    """Return a flat list of all issues."""
    issues = []

    issues.extend(find_digits_outside_math(text))
    issues.extend(find_single_letters_outside_math(text))
    issues.extend(find_commas_colons_inside_math(text))
    issues.extend(find_spacing_around_punctuation(text))
    issues.extend(find_spacing_inside_delimiters(text))
    issues.extend(find_double_backslashes(text))

    # De-duplicate by (kind, index) and sort
    seen = set()
    unique = []
    for issue in issues:
        key = (issue["kind"], issue["index"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(issue)

    unique.sort(key=lambda x: x["index"])
    return unique
