# app.py
from flask import Flask, render_template, request
from collections import defaultdict
from pathlib import Path
import markdown


from latex_checker import (
    analyze_text,
    fix_double_backslashes,
    fix_numbers_into_math,
    fix_remove_bold_commands,
    fix_spacing_before_punctuation,
    fix_spacing_inside_delimiters,
)

app = Flask(__name__)


def escape_char(ch: str) -> str:
    if ch == "&":
        return "&amp;"
    if ch == "<":
        return "&lt;"
    if ch == ">":
        return "&gt;"
    if ch == '"':
        return "&quot;"
    if ch == "'":
        return "&#39;"
    return ch


def highlight_text(text: str, issues):
    """Return HTML for the highlighted LaTeX with line numbers."""
    index_to_kinds = defaultdict(list)
    for issue in issues:
        length = issue.get("length", 1)
        start = issue["index"]
        for idx in range(start, min(start + length, len(text))):
            index_to_kinds[idx].append(issue["kind"])

    lines = text.split("\n")
    html_lines = []
    idx = 0

    for line_no, line in enumerate(lines, start=1):
        char_pieces = []

        for ch in line:
            html_ch = escape_char(ch)
            kinds = index_to_kinds.get(idx)

            if kinds:
                classes = " ".join(sorted({f"issue-{k}" for k in kinds}))
                title = ", ".join(sorted(set(kinds)))
                char_pieces.append(
                    f'<span class="{classes}" title="{title}">{html_ch}</span>'
                )
            else:
                char_pieces.append(html_ch)

            idx += 1

        content_html = "".join(char_pieces) or "&nbsp;"

        html_lines.append(
            f'<div class="code-line">'
            f'<span class="code-line-number">{line_no}</span>'
            f'<span class="code-line-content">{content_html}</span>'
            f"</div>"
        )

        if idx < len(text) and text[idx] == "\n":
            idx += 1

    return "".join(html_lines)


@app.route("/", methods=["GET", "POST"])
def index():
    text = ""
    issues = []
    highlighted = ""
    fix_message = ""

    if request.method == "POST":
        text = request.form.get("latex", "")
        action = request.form.get("action", "check")

        if action == "fix_all":
            # Apply fixes in an order that minimizes interference.
            # 1) Remove \boldsymbol / \mathbf wrappers
            # 2) Remove/convert \\ tokens
            # 3) Remove spacing just inside quotes/parentheses
            # 4) Remove spaces before punctuation
            # 5) Wrap numeric tokens in $...$
            text, bd = fix_remove_bold_commands(text)
            text, bs = fix_double_backslashes(text)
            text, ds = fix_spacing_inside_delimiters(text)
            text, ps = fix_spacing_before_punctuation(text)
            text, ns = fix_numbers_into_math(text)

            changed = (bd["removed"] + bs["removed"] + bs["replaced"] + ds["removed"] + ps["removed"] + ns["wrapped"]) > 0
            if changed:
                fix_message = (
                    "Fix all applied: "
                    f"bold {bd['removed']}; \\\\ removed {bs['removed']}; converted to \\cr {bs['replaced']}; "
                    f"delims {ds['removed']}; punct {ps['removed']}; numbers {ns['wrapped']}."
                )
            else:
                fix_message = "Fix all: no changes needed."

        elif action == "fix_backslash":
            text, stats = fix_double_backslashes(text)
            fix_message = (
                f"Fixed \\\\: removed {stats['removed']} outside math; "
                f"replaced {stats['replaced']} inside math with \\cr."
            )
        elif action == "fix_delims":
            text, stats = fix_spacing_inside_delimiters(text)
            fix_message = f"Fixed delimiter spacing: removed {stats['removed']} space(s)."
        elif action == "fix_punct":
            text, stats = fix_spacing_before_punctuation(text)
            fix_message = f"Fixed punctuation spacing: removed {stats['removed']} space(s)."
        elif action == "fix_numbers":
            text, stats = fix_numbers_into_math(text)
            fix_message = f"Fixed numbers: wrapped {stats['wrapped']} number(s) in $...$."
        elif action == "fix_bold":
            text, stats = fix_remove_bold_commands(text)
            fix_message = f"Fixed bold commands: removed {stats['removed']} wrapper(s)."
        # else: "check" or unknown -> no modification

        issues = analyze_text(text)
        highlighted = highlight_text(text, issues)

    return render_template(
        "index.html",
        text=text,
        issues=issues,
        highlighted=highlighted,
        fix_message=fix_message,
    )

@app.get("/help")
def help_page():
    md_path = Path(app.root_path) / "USAGE.md"
    if md_path.exists():
        md_text = md_path.read_text(encoding="utf-8")
    else:
        md_text = "# USAGE\n\nUSAGE.md not found."

    html = markdown.markdown(
        md_text,
        extensions=["fenced_code", "tables", "toc"]
    )

    return render_template("help.html", content=html)

if __name__ == "__main__":
    app.run(debug=True)
