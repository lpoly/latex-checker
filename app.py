# app.py
from flask import Flask, render_template, request
from collections import defaultdict
from pathlib import Path
import markdown


from latex_checker import (
    analyze_text,
    analyze_problem_statement,
    fix_double_backslashes,
    fix_numbers_into_math,
    fix_remove_bold_commands,
    fix_spacing_before_punctuation,
    fix_spacing_inside_delimiters,
    fix_bmod_to_pmod,
    fix_naked_math_envs,
    fix_table_to_array,
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
    problem_text = ""
    solution_text = ""
    problem_issues = []
    solution_issues = []
    problem_highlighted = ""
    solution_highlighted = ""
    fix_message = ""

    if request.method == "POST":
        problem_text = request.form.get("problem_text", "")
        solution_text = request.form.get("solution_text", "")
        action = request.form.get("action", "check")

        if action == "fix_all":
            problem_text,  pbd = fix_remove_bold_commands(problem_text)
            problem_text,  pbs = fix_double_backslashes(problem_text)
            problem_text,  pds = fix_spacing_inside_delimiters(problem_text)
            problem_text,  pps = fix_spacing_before_punctuation(problem_text)
            problem_text,  pbm = fix_bmod_to_pmod(problem_text)
            problem_text,  pen = fix_naked_math_envs(problem_text)
            problem_text,  ptb = fix_table_to_array(problem_text)
            problem_text,  pns = fix_numbers_into_math(problem_text)
            solution_text, sbd = fix_remove_bold_commands(solution_text)
            solution_text, sbs = fix_double_backslashes(solution_text)
            solution_text, sds = fix_spacing_inside_delimiters(solution_text)
            solution_text, sps = fix_spacing_before_punctuation(solution_text)
            solution_text, sbm = fix_bmod_to_pmod(solution_text)
            solution_text, sen = fix_naked_math_envs(solution_text)
            solution_text, stb = fix_table_to_array(solution_text)
            solution_text, sns = fix_numbers_into_math(solution_text)
            total_bold    = pbd["removed"]   + sbd["removed"]
            total_bs_rem  = pbs["removed"]   + sbs["removed"]
            total_bs_rep  = pbs["replaced"]  + sbs["replaced"]
            total_delims  = pds["removed"]   + sds["removed"]
            total_punct   = pps["removed"]   + sps["removed"]
            total_nums    = pns["wrapped"]   + sns["wrapped"]
            total_bmod    = pbm["replaced"]  + sbm["replaced"]
            total_env     = pen["wrapped"]   + sen["wrapped"]
            total_table   = ptb["replaced"]  + stb["replaced"]
            changed = (total_bold + total_bs_rem + total_bs_rep + total_delims + total_punct + total_nums + total_bmod + total_env + total_table) > 0
            if changed:
                fix_message = (
                    f"Fix all: bold {total_bold}; \\\\ removed {total_bs_rem}; "
                    f"converted to \\cr {total_bs_rep}; delims {total_delims}; "
                    f"punct {total_punct}; numbers {total_nums}; bmod {total_bmod}; "
                    f"env {total_env}; table {total_table}."
                )
            else:
                fix_message = "Fix all: no changes needed."

        elif action == "fix_backslash":
            problem_text,  ps = fix_double_backslashes(problem_text)
            solution_text, ss = fix_double_backslashes(solution_text)
            fix_message = (
                f"Fixed \\\\: removed {ps['removed'] + ss['removed']}; "
                f"replaced with \\cr {ps['replaced'] + ss['replaced']}."
            )
        elif action == "fix_delims":
            problem_text,  ps = fix_spacing_inside_delimiters(problem_text)
            solution_text, ss = fix_spacing_inside_delimiters(solution_text)
            fix_message = f"Fixed delimiter spacing: removed {ps['removed'] + ss['removed']} space(s)."
        elif action == "fix_punct":
            problem_text,  ps = fix_spacing_before_punctuation(problem_text)
            solution_text, ss = fix_spacing_before_punctuation(solution_text)
            fix_message = f"Fixed punctuation spacing: removed {ps['removed'] + ss['removed']} space(s)."
        elif action == "fix_numbers":
            problem_text,  ps = fix_numbers_into_math(problem_text)
            solution_text, ss = fix_numbers_into_math(solution_text)
            fix_message = f"Fixed numbers: wrapped {ps['wrapped'] + ss['wrapped']} number(s) in $...$."
        elif action == "fix_bold":
            problem_text,  ps = fix_remove_bold_commands(problem_text)
            solution_text, ss = fix_remove_bold_commands(solution_text)
            fix_message = f"Fixed bold: removed {ps['removed'] + ss['removed']} wrapper(s)."
        elif action == "fix_bmod":
            problem_text,  ps = fix_bmod_to_pmod(problem_text)
            solution_text, ss = fix_bmod_to_pmod(solution_text)
            fix_message = f"Fixed bmod: replaced {ps['replaced'] + ss['replaced']} instance(s) with \\pmod."
        elif action == "fix_env":
            problem_text,  ps = fix_naked_math_envs(problem_text)
            solution_text, ss = fix_naked_math_envs(solution_text)
            fix_message = f"Fixed env: wrapped {ps['wrapped'] + ss['wrapped']} environment(s) with $$."
        elif action == "fix_table":
            problem_text,  ps = fix_table_to_array(problem_text)
            solution_text, ss = fix_table_to_array(solution_text)
            fix_message = f"Fixed table: replaced {ps['replaced'] + ss['replaced']} table(s) with array."
        # else: "check" or unknown -> no modification

        if problem_text:
            problem_issues = analyze_problem_statement(problem_text)
            problem_highlighted = highlight_text(problem_text, problem_issues)
        if solution_text:
            solution_issues = analyze_text(solution_text)
            solution_highlighted = highlight_text(solution_text, solution_issues)

    return render_template(
        "index.html",
        problem_text=problem_text,
        problem_issues=problem_issues,
        problem_highlighted=problem_highlighted,
        solution_text=solution_text,
        solution_issues=solution_issues,
        solution_highlighted=solution_highlighted,
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
