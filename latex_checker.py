# latex_checker.py
import re
from bisect import bisect_right

MATH_ENVS = [
    "array",
    "align", "align*",
    "gather", "gather*", "equation"
]

ENV_PATTERN = re.compile(
    r'\\begin\{(' + '|'.join(re.escape(e) for e in MATH_ENVS) + r')\}'
    r'.*?'
    r'\\end\{\1\}',
    re.DOTALL
)

DISPLAY_MATH_PATTERNS = [
    re.compile(r'\$\$.*?\$\$', re.DOTALL),        # $$ ... $$
    re.compile(r'\\\[.*?\\\]', re.DOTALL),        # \[ ... \]
    ENV_PATTERN,                                  # math environments
]

INLINE_MATH_PATTERNS = [
    re.compile(r'\\\(.*?\\\)', re.DOTALL),                 # \( ... \)
    re.compile(r'(?<!\$)\$(?!\$).*?(?<!\$)\$(?!\$)', re.DOTALL),  # $ ... $ (single $)
]

MATH_PATTERNS = DISPLAY_MATH_PATTERNS + INLINE_MATH_PATTERNS

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
    r"""
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

def get_math_regions(text: str, patterns=None):
    """
    Return a list of (start, end) index pairs for math regions in the text.
    """
    if patterns is None:
        patterns = MATH_PATTERNS

    chars = list(text)
    work_text = text
    regions = []

    for pattern in patterns:
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

    NOTE: we allow punctuation immediately followed by a quote, e.g.
      Hello,"this is an example"
    """
    math_mask = get_math_mask(text)
    line_starts = build_line_starts(text)
    lines = text.splitlines()

    punctuation = ".,;:!?"
    closing_chars = '")\']}>”’'  # chars we can skip AFTER the punctuation
    quote_chars = '"“”‘’\''      # chars we treat as OK immediately after punct

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
        missing_space_after = False

        if idx + 1 < n:
            next_immediate = text[idx + 1]

            # Case: punctuation immediately followed by a quote => allow
            if next_immediate in quote_chars:
                missing_space_after = False
            else:
                # Skip over closing brackets/quotes etc. (for things like ".) ")
                j = idx + 1
                while j < n and text[j] in closing_chars:
                    j += 1

                if j < n:
                    next_ch = text[j]
                    # If the next "real" char is not whitespace, we expect a space
                    if next_ch not in " \t\n\r":
                        missing_space_after = True
                # If j >= n: punctuation at end-of-text -> OK
        # else: punctuation at very end of text -> OK

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
    r"""
    Find commas/colons inside inline math only, EXCEPT when they appear
    inside groupings like \{ ... \}, (...) or [...].

    Display math is intentionally ignored because punctuation is commonly
    acceptable there.
    """
    math_regions = get_math_regions(text, INLINE_MATH_PATTERNS)
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

    left_delims = '([“‘'
    right_delims = ')]”’'

    results = []
    seen = set()
    n = len(text)
    straight_quote_open = False

    def add_issue(space_idx: int):
        if not (0 <= space_idx < n):
            return
        if space_idx in seen:
            return
        if text[space_idx] != ' ':
            return
        if space_idx < len(math_mask) and math_mask[space_idx]:
            return

        line_no, col_no = index_to_line_col(space_idx, line_starts)
        line_text = lines[line_no - 1] if 1 <= line_no <= len(lines) else ""
        results.append({
            "kind": "spacing",
            "index": space_idx,
            "line": line_no,
            "col": col_no,
            "char": "␣",
            "line_text": line_text,
        })
        seen.add(space_idx)

    for idx, ch in enumerate(text):
        if idx < len(math_mask) and math_mask[idx]:
            continue

        if ch in left_delims:
            add_issue(idx + 1)
        elif ch in right_delims:
            add_issue(idx - 1)
        elif ch == '"':
            if straight_quote_open:
                add_issue(idx - 1)
                straight_quote_open = False
            else:
                add_issue(idx + 1)
                straight_quote_open = True

    return results


def fix_double_backslashes(text: str):
    r"""Auto-fix LaTeX line breaks (\\) depending on math mode.

    Rules:
      - Outside math mode: delete the \\ token.
      - Inside math mode: replace each \\ token with \cr.

    Returns:
      (new_text, stats) where stats = {"removed": int, "replaced": int}
    """
    if not text:
        return text, {"removed": 0, "replaced": 0}

    math_mask = get_math_mask(text)
    out = []
    i = 0
    n = len(text)
    removed = 0
    replaced = 0

    while i < n:
        if i < n - 1 and text[i] == "\\" and text[i + 1] == "\\":
            in_math = (
                (i < len(math_mask) and math_mask[i])
                or (i + 1 < len(math_mask) and math_mask[i + 1])
            )
            if in_math:
                out.append("\\cr ")
                replaced += 1
            else:
                removed += 1
                # Outside math: convert \\ into a real line break.
                # Avoid creating an extra blank line if a newline already follows. (feature removed)
                next_ch = text[i + 2] if (i + 2) < n else ""
                out.append("\n")
            i += 2
            continue

        out.append(text[i])
        i += 1

    return "".join(out), {"removed": removed, "replaced": replaced}


def fix_spacing_inside_delimiters(text: str):
    """Remove spaces/tabs just inside quotes/parentheses OUTSIDE math.

    Returns:
      (new_text, stats) where stats = {"removed": int}
    """
    if not text:
        return text, {"removed": 0}

    math_mask = get_math_mask(text)

    left_parens = set('([')
    right_parens = set(')]')

    # Curly quotes have inherent direction; straight quote (") is ambiguous.
    open_quotes = set('“‘')
    close_quotes = set('”’')

    out = []
    removed = 0
    i = 0
    n = len(text)
    straight_quote_open = False

    while i < n:
        if i < len(math_mask) and math_mask[i]:
            out.append(text[i])
            i += 1
            continue

        ch = text[i]

        # Parentheses/brackets
        if ch in right_parens:
            while out and out[-1] in (' ', '\t'):
                out.pop()
                removed += 1
            out.append(ch)
            i += 1
            continue

        if ch in left_parens:
            out.append(ch)
            i += 1
            while i < n and (i < len(math_mask) and not math_mask[i]) and text[i] in (' ', '\t'):
                removed += 1
                i += 1
            continue

        # Quotes
        if ch in open_quotes:
            out.append(ch)
            i += 1
            while i < n and (i < len(math_mask) and not math_mask[i]) and text[i] in (' ', '\t'):
                removed += 1
                i += 1
            continue

        if ch in close_quotes:
            while out and out[-1] in (' ', '\t'):
                out.pop()
                removed += 1
            out.append(ch)
            i += 1
            continue

        if ch == '"':
            if straight_quote_open:
                while out and out[-1] in (' ', '\t'):
                    out.pop()
                    removed += 1
                out.append(ch)
                straight_quote_open = False
                i += 1
                continue
            else:
                out.append(ch)
                straight_quote_open = True
                i += 1
                while i < n and (i < len(math_mask) and not math_mask[i]) and text[i] in (' ', '\t'):
                    removed += 1
                    i += 1
                continue

        out.append(ch)
        i += 1

    return "".join(out), {"removed": removed}


def fix_spacing_before_punctuation(text: str):
    """Remove spaces/tabs immediately before punctuation OUTSIDE math.

    Punctuation: . , ; : ! ?

    Returns:
      (new_text, stats) where stats = {"removed": int}
    """
    if not text:
        return text, {"removed": 0}

    math_mask = get_math_mask(text)
    punctuation = set('.,;:!?')

    out = []
    removed = 0
    i = 0
    n = len(text)

    while i < n:
        if i < len(math_mask) and math_mask[i]:
            out.append(text[i])
            i += 1
            continue

        ch = text[i]
        if ch in punctuation:
            while out and out[-1] in (' ', '\t'):
                out.pop()
                removed += 1
            out.append(ch)
            i += 1
            continue

        out.append(ch)
        i += 1

    return "".join(out), {"removed": removed}


def fix_numbers_into_math(text: str):
    r"""Wrap number tokens outside math mode in $...$.

    Behavior:
      - Wraps numbers even inside plain brackets/braces, e.g. [1] -> [$1$]
      - Absorbs unary +/- when it is immediately before the number:
          "-1" -> "$-1$", "+2" -> "$+2$"
      - Skips numbers inside *LaTeX command arguments* (required {...} and optional [...] args),
        e.g. \cite{2020}, \item[1], \href{...}{2020}.

    Returns:
      (new_text, stats) where stats = {"wrapped": int}
    """
    if not text:
        return text, {"wrapped": 0}

    math_mask = get_math_mask(text)
    out = []
    wrapped = 0
    n = len(text)
    i = 0

    # Track whether we're inside a command argument (so we don't break \cite{2020}, etc.)
    brace_cmd_stack = []     # stack of bools: does this { ... } belong to a command arg?
    bracket_cmd_stack = []   # stack of bools: does this [ ... ] belong to a command opt arg?
    cmd_arg_level = 0        # >0 means we're inside at least one command arg
    last_cmd_arg_close = None  # index of a '}' that closed a command arg (for multi-arg commands)

    def is_escaped(idx: int) -> bool:
        return idx > 0 and text[idx - 1] == '\\'

    def is_outside_math(idx: int) -> bool:
        return not (0 <= idx < len(math_mask) and math_mask[idx])

    def skip_ws_left(j: int) -> int:
        while j >= 0 and text[j] in " \t\r\n":
            j -= 1
        return j

    def strip_one_optional_arg_ending_at(j: int) -> int:
        """If text[j] == ']' (not escaped), move j left to just before matching '[' (skipping nested [])."""
        if j < 0 or text[j] != ']' or is_escaped(j):
            return j
        depth = 1
        k = j - 1
        while k >= 0:
            if text[k] == ']' and not is_escaped(k):
                depth += 1
            elif text[k] == '[' and not is_escaped(k):
                depth -= 1
                if depth == 0:
                    return skip_ws_left(k - 1)
            k -= 1
        return j  # unmatched; leave as-is

    def preceded_by_control_sequence(pos: int) -> bool:
        """Heuristic: is there a TeX control sequence immediately before pos (skipping whitespace and optional args)?"""
        j = skip_ws_left(pos - 1)
        if j < 0:
            return False

        # If we're after one or more optional args: \cmd[...][...]{...}
        while j >= 0 and text[j] == ']' and not is_escaped(j):
            new_j = strip_one_optional_arg_ending_at(j)
            if new_j == j:
                break
            j = new_j

        # Optional star: \section*{...}
        if j >= 0 and text[j] == '*':
            j = skip_ws_left(j - 1)

        if j < 0:
            return False

        # Control word: \command
        if text[j].isalpha():
            k = j
            while k >= 0 and text[k].isalpha():
                k -= 1
            return k >= 0 and text[k] == '\\' and not is_escaped(k)

        # Control symbol: \, \% etc. (rare before args, but harmless to detect)
        return j >= 1 and text[j - 1] == '\\' and not is_escaped(j - 1)

    def is_cmd_required_arg_open(pos: int) -> bool:
        # normal case: \cmd{...}
        if preceded_by_control_sequence(pos):
            return True
        # multi-arg case: \cmd{...}{...}  -> treat subsequent { as command args too if only whitespace between
        if last_cmd_arg_close is not None:
            k = last_cmd_arg_close + 1
            while k < pos and text[k] in " \t\r\n":
                k += 1
            if k == pos:  # only whitespace between
                return True
        return False

    def is_cmd_optional_arg_open(pos: int) -> bool:
        # optional args generally follow the control sequence directly: \cmd[...]
        return preceded_by_control_sequence(pos)

    while i < n:
        # Always pass through math-mode text unchanged
        if i < len(math_mask) and math_mask[i]:
            out.append(text[i])
            i += 1
            continue

        ch = text[i]

        # Track command-argument contexts for { } and [ ]
        if ch == '{' and not is_escaped(i):
            is_cmd = is_cmd_required_arg_open(i)
            brace_cmd_stack.append(is_cmd)
            if is_cmd:
                cmd_arg_level += 1
            out.append(ch)
            i += 1
            continue

        if ch == '}' and not is_escaped(i):
            is_cmd = brace_cmd_stack.pop() if brace_cmd_stack else False
            if is_cmd and cmd_arg_level > 0:
                cmd_arg_level -= 1
                last_cmd_arg_close = i
            else:
                # if we closed a non-command brace, don't keep last_cmd_arg_close "armed"
                last_cmd_arg_close = None
            out.append(ch)
            i += 1
            continue

        if ch == '[' and not is_escaped(i):
            is_cmd = is_cmd_optional_arg_open(i)
            bracket_cmd_stack.append(is_cmd)
            if is_cmd:
                cmd_arg_level += 1
            out.append(ch)
            i += 1
            continue

        if ch == ']' and not is_escaped(i):
            is_cmd = bracket_cmd_stack.pop() if bracket_cmd_stack else False
            if is_cmd and cmd_arg_level > 0:
                cmd_arg_level -= 1
            out.append(ch)
            i += 1
            continue

        # Any non-whitespace character resets the "multi-arg" brace chaining unless it's '{' (handled above)
        if ch not in " \t\r\n":
            last_cmd_arg_close = None

        # Wrap digits (outside math) unless we're inside a command argument
        if ch.isdigit() and cmd_arg_level == 0:
            start = i
            sign_absorbed = False

            # Absorb unary +/-
            if i > 0 and is_outside_math(i - 1) and text[i - 1] in "+-" and not is_escaped(i - 1):
                prev = text[i - 2] if i - 2 >= 0 else ""
                unary_boundary = (i - 2 < 0) or prev.isspace() or (prev in "([{\"'=,;:\n\r\t")
                if unary_boundary:
                    start = i - 1
                    sign_absorbed = True

            # Left boundary: avoid wrapping digits embedded in words/commands
            if start > 0 and is_outside_math(start - 1) and (text[start - 1].isalnum() or text[start - 1] == '\\'):
                out.append(ch)
                i += 1
                continue

            # Scan numeric token (digits + optional grouped/decimal separators)
            j = i
            while j < n and is_outside_math(j) and text[j].isdigit():
                j += 1

            while (
                j + 1 < n
                and is_outside_math(j)
                and text[j] in '.,'
                and is_outside_math(j + 1)
                and text[j + 1].isdigit()
            ):
                j += 1
                while j < n and is_outside_math(j) and text[j].isdigit():
                    j += 1

            token = text[start:j]

            # Right boundary: avoid wrapping if followed by alphanumeric
            if j < n and is_outside_math(j) and text[j].isalnum():
                out.append(ch)
                i += 1
                continue

            # If we absorbed a sign, remove the already-emitted sign char before wrapping
            if sign_absorbed and out and out[-1] == text[start]:
                out.pop()

            out.append(f"${token}$")
            wrapped += 1
            i = j
            continue

        out.append(ch)
        i += 1

    return "".join(out), {"wrapped": wrapped}


def fix_remove_bold_commands(text: str):
    r"""Remove \boldsymbol and \mathbf wrappers while keeping their contents.

    Examples:
      \mathbf{A} -> A
      \boldsymbol{x+y} -> x+y
      \mathbf\alpha -> \alpha

    Returns:
      (new_text, stats) where stats = {"removed": int}
    """
    if not text:
        return text, {"removed": 0}

    commands = ("\\boldsymbol", "\\mathbf")
    out = []
    i = 0
    n = len(text)
    removed = 0

    while i < n:
        matched = None
        for cmd in commands:
            if text.startswith(cmd, i):
                matched = cmd
                break

        if not matched:
            out.append(text[i])
            i += 1
            continue

        removed += 1
        i += len(matched)

        while i < n and text[i] in " \t\r\n":
            i += 1

        if i < n and text[i] == "{":
            depth = 1
            i += 1
            start = i

            while i < n and depth > 0:
                if text[i] == "{" and (i == 0 or text[i - 1] != "\\"):
                    depth += 1
                elif text[i] == "}" and (i == 0 or text[i - 1] != "\\"):
                    depth -= 1
                    if depth == 0:
                        out.append(text[start:i])
                        i += 1
                        break
                i += 1
            else:
                out.append(matched)
        else:
            if i < n and text[i] == "\\":
                start = i
                i += 1
                while i < n and text[i].isalpha():
                    i += 1
                out.append(text[start:i])
            elif i < n:
                out.append(text[i])
                i += 1

    return "".join(out), {"removed": removed}


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
