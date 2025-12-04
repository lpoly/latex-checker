# app.py
from flask import Flask, render_template, request
from html import escape as html_escape
from collections import defaultdict
from latex_checker import analyze_text

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
    """
    Return HTML for the highlighted LaTeX with line numbers.

    Each line is rendered as:
      <div class="code-line">
        <span class="code-line-number">N</span>
        <span class="code-line-content">...highlighted chars...</span>
      </div>
    """
    # Map each character index -> list of "kinds" (digit, letter, punct, backslash, etc.)
    index_to_kinds = defaultdict(list)
    for issue in issues:
        length = issue.get("length", 1)
        start = issue["index"]
        for idx in range(start, min(start + length, len(text))):
            index_to_kinds[idx].append(issue["kind"])

    lines = text.split("\n")
    html_lines = []
    idx = 0  # absolute index in original text

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

        # keep empty lines visible
        content_html = "".join(char_pieces) or "&nbsp;"

        html_lines.append(
            f'<div class="code-line">'
            f'<span class="code-line-number">{line_no}</span>'
            f'<span class="code-line-content">{content_html}</span>'
            f'</div>'
        )

        # skip the newline character itself
        if idx < len(text) and text[idx] == "\n":
            idx += 1

    return "".join(html_lines)




@app.route("/", methods=["GET", "POST"])
def index():
    text = ""
    issues = []
    highlighted = ""

    if request.method == "POST":
        text = request.form.get("latex", "")
        issues = analyze_text(text)
        highlighted = highlight_text(text, issues)

    return render_template(
        "index.html",
        text=text,
        issues=issues,
        highlighted=highlighted,
    )


if __name__ == "__main__":
    app.run(debug=True)
