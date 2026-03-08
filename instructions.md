# LaTeX Checker – Project Overview

This document summarizes the LaTeX checker web app: what it does, how it works, and the main design choices. It’s written so someone new (or another AI assistant) can quickly understand and extend the project.

---

## 1. Goal

The LaTeX checker is a small web tool to catch **careless transcription mistakes** in LaTeX before problems are submitted for QA.

It focuses on a handful of error patterns that are easy to miss manually but important for consistency:

- Digits that are outside math mode.
- Stray single letters (likely variables) that should be in math.
- Suspicious commas/colons in math expressions.
- Spacing mistakes around punctuation and delimiters.
- LaTeX line breaks (`\\`) that should be checked.

The app is:

- A **Flask** backend that analyzes LaTeX text.
- A **frontend** using HTML/CSS and **CodeMirror** for the editor.
- Deployed on **Render** (free tier) and backed by a GitHub repo.

---

## 2. Backend: `latex_checker.py`

The backend is responsible for scanning a LaTeX string and returning a list of issues, as well as providing data used to build the highlighted output.

### 2.1 Data model

The central function is:

```python
analyze_text(text: str) -> list[dict]
````

It returns a list of issue dictionaries, each with:

```python
{
    "kind": "digit" | "letter" | "punct" | "spacing" | "backslash",
    "index": int,      # absolute character index in the original string
    "line": int,       # 1-based line number
    "col": int,        # 1-based column number
    "char": str,       # offending character or a symbol (e.g. "␣" for space)
    "line_text": str,  # the full text of that line
    # "length": int    # only for backslashes, length of the '\\' sequence
}
```

The backend also provides helpers to map indices to `(line, col)` and to distinguish text from math.

---

### 2.2 Detecting math regions

Math regions are defined as:

* `$$ ... $$`
* `\[ ... \]`
* `\( ... \)`
* LaTeX math environments such as:

  * `\begin{array}...\end{array}`
  * `\begin{align}...\end{align}`
  * `\begin{gather}...\end{gather}`
  * `\begin{equation}...\end{equation}`
* `$ ... $` (single-dollar inline math, but not `$$`).

Key globals:

```python
MATH_ENVS = [
    "array",
    "align", "align*",
    "gather", "gather*", "equation",
]

MATH_PATTERNS = [
    re.compile(r'\$\$.*?\$\$', re.DOTALL),
    re.compile(r'\\\[.*?\\\]', re.DOTALL),
    re.compile(r'\\\(.*?\\\)', re.DOTALL),
    ENV_PATTERN,  # \begin{...}...\end{...}
    re.compile(r'\$(?!\$).*?\$', re.DOTALL),
]
```

Helper functions:

* **`mask_math_regions(text) -> str`**
  Returns a new string of the same length where characters inside math are replaced with spaces (except newlines). This is used for checks that should only see **text outside math** while preserving character indices.

* **`get_math_mask(text) -> list[bool]`**
  Returns a boolean list `math_mask` where `math_mask[i]` is `True` if the character at position `i` is inside a math region. Used when checks need to treat math and text differently.

* **`get_math_regions(text) -> list[tuple[int, int]]`**
  Returns a list of `(start, end)` index pairs for each math region. Used for more involved parsing inside math (e.g. tracking nested brackets).

Line helpers:

* **`build_line_starts(text)`** – return the index where each line starts.
* **`index_to_line_col(idx, line_starts)`** – map an absolute index to `(line_no, col_no)`.

All checks rely on these to stay index-accurate.

---

### 2.3 Individual checks

#### 2.3.1 Digits outside math (`kind: "digit"`)

**Purpose:** flag numbers that appear in text, which often should be math (e.g. `n=2` written as plain text).

Implementation:

1. Call `mask_math_regions(text)` so digits inside math are replaced by spaces.
2. Use a simple digit regex:

   ```python
   for m in re.finditer(r'\d', masked):
       idx = m.start()
       # convert idx to (line, col) and record the issue
   ```

Effect: digits in `$n=2$` are hidden; digits in normal text lines are flagged.

---

#### 2.3.2 Single letters outside math (`kind: "letter"`)

**Purpose:** flag stray single letters like `x` or `y` in text, which likely should be in math mode.

You use:

```python
SINGLE_LETTER_PATTERN = re.compile(
    r'\b([B-HJ-Zb-hj-z])\b(?=[\s\.,;:!?])'
)
```

Notes:

* It matches single letters *excluding* `A`, `I`, and their lowercase forms (since those are very common English words).
* It requires a word boundary and that the next character is whitespace or punctuation.

Implementation:

1. Run the regex on `masked = mask_math_regions(text)`.
2. Take `group(1)` as the offending letter and record.

So lone letters outside math are tagged, but “I” and “A” are not.

---

#### 2.3.3 Commas and colons inside math (`kind: "punct"`)

**Goal:** flag “loose” commas and colons in math, but **do not** flag those that are clearly part of groupings like `\{a, b\}`, `(a, b)`, `[a, b]`.

To achieve this, you use **stack-based scanning** per math region:

1. Use `get_math_regions(text)` to get all math intervals.
2. For each `(start, end)`:

   * Initialize an empty `stack`.
   * Walk from `start` to `end`:

     * On seeing `\{` → push `"brace"`.
     * On seeing `(` → push `"paren"`.
     * On seeing `[` → push `"bracket"`.
     * On seeing `\}` → if top is `"brace"`, pop.
     * On seeing `)` → if top is `"paren"`, pop.
     * On seeing `]` → if top is `"bracket"`, pop.
   * When encountering `,` or `:`:

     * If `stack` is **empty** → top-level punctuation → **flag** this as a `kind: "punct"` issue.
     * If `stack` is not empty → punctuation is inside a group → **skip** it.

This way:

* `$a,b$` → comma flagged (top-level).
* `$f(x,y) = 1:2$` → both comma and colon at top level (depending on structure) can be flagged.
* `$ \{ a, b \}$`, `$ (x, y) $`, `$ [u, v] $` → commas **not flagged** because they are inside braces, parentheses, or brackets.

---

#### 2.3.4 Spacing around punctuation outside math (`kind: "spacing"`)

**Goal:** enforce clean spacing around punctuation in text:

* No space **before** punctuation: `word ,like` is bad.
* Space **after** punctuation: `word,bad` is bad.
* Allow punctuation immediately followed by a quote, e.g. `Hello,"this ..."` is okay.

Logic:

1. Compute `math_mask`.

2. For each character `ch` in `text`:

   * If `ch` not in `.,;:!?`, skip.
   * If `math_mask[idx]` is `True`, skip (we ignore punctuation in math).

3. Check two conditions:

   * **`has_space_before`** – if `idx > 0 and text[idx-1] == ' '`.
   * **`missing_space_after`**:

     * Look at `next_immediate = text[idx+1]` if it exists.
     * If `next_immediate` is a quote (from a set like `"“”‘’'`), treat this as okay (no missing space).
     * Otherwise, skip over closing delimiters (`")']}>”’`) to find the next “real” character.
     * If that character exists and is *not* whitespace, we consider the space after punctuation missing.

4. If either:

   * `has_space_before` is `True`, or
   * `missing_space_after` is `True`,
     then add a `kind: "spacing"` issue for that punctuation.

Examples:

* `Hello ,world` → space before comma → flagged.
* `Hello,world` → missing space after → flagged.
* `Hello, world` → correct; no issue.
* `Hello,"this is fine"` → allowed; no issue.

---

#### 2.3.5 Spacing inside delimiters (`kind: "spacing"`)

**Goal:** catch extra spaces just inside parentheses or quotes in text, such as:

* `( example )`
* `" example "`

Implementation:

1. Compute `math_mask`.

2. For each character in `text`:

   * Only consider `' '` (space).
   * If `math_mask[idx]` is `True`, skip (we ignore math).

3. Define:

   ```python
   left_delims = '(["“‘'
   right_delims = ')]"”’'
   ```

4. A space is problematic if:

   * it comes immediately **after** an opening delimiter (e.g. `"( "`), or
   * it comes immediately **before** a closing delimiter (e.g. `" )"`).

5. For such spaces, record a `kind: "spacing"` issue with `"char": "␣"` to make it obvious it’s about a space.

---

#### 2.3.6 Double backslashes (`kind: "backslash"`)

**Goal:** detect `\\` sequences (LaTeX line breaks) both inside and outside math.

Implementation:

* Walk the text with an index `i`.
* If `text[i] == "\\"` and `text[i+1] == "\\"`:

  * record a `kind: "backslash"` issue at position `i` with `char: "\\\\"` and `length: 2`.
  * increment `i` by 2.
* Otherwise, increment `i` by 1.

No math checks are used here – `\\` is always flagged.

---

### 2.4 Putting it together: `analyze_text`

The central orchestrator:

```python
def analyze_text(text: str):
    issues = []

    issues.extend(find_digits_outside_math(text))
    issues.extend(find_single_letters_outside_math(text))
    issues.extend(find_commas_colons_inside_math(text))
    issues.extend(find_spacing_around_punctuation(text))
    issues.extend(find_spacing_inside_delimiters(text))
    issues.extend(find_double_backslashes(text))

    # De-duplicate by (kind, index)
    seen = set()
    unique = []
    for issue in issues:
        key = (issue["kind"], issue["index"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(issue)

    # Sort by index so highlighting is easier to build
    unique.sort(key=lambda x: x["index"])
    return unique
```

All frontend highlighting and issue listing is driven by this one function.

---

## 3. Flask app and frontend

### 3.1 Flask app (`app.py`)

The Flask app exposes a single route:

```python
@app.route("/", methods=["GET", "POST"])
def index():
    text = ""
    highlighted = ""
    issues = []

    if request.method == "POST":
        text = request.form.get("latex", "")
        issues = analyze_text(text)
        highlighted = highlight_text(text, issues)

    return render_template(
        "index.html",
        text=text,
        highlighted=highlighted,
        issues=issues,
    )
```

Key points:

* On **GET**, `text` is empty → input panel is blank; right panel shows a placeholder.
* On **POST**, the app:

  * reads the input LaTeX,
  * runs `analyze_text`,
  * calls `highlight_text(text, issues)` which inserts `<span class="issue-...">` wrappers at issue positions,
  * returns these to the template.

`highlight_text` uses the `kind` to choose classes like `issue-digit`, `issue-spacing`, etc., so the CSS can color them differently.

---

### 3.2 Frontend HTML (`templates/index.html`)

The main structure is:

* A header with title and description.
* A `section.panels` with two `.panel` blocks side by side:

  * Left: input editor.
  * Right: highlighted output.
* A `section.issues-section` listing all issues in text form.

Key portions:

```html
<section class="panels" id="panels">
  <!-- Input panel -->
  <div class="panel">
    <div class="panel-header">
      <h2>Input Text</h2>
      <span class="panel-tag">Source</span>
    </div>

    <form method="post" action="#panels" class="checker-form">
      <textarea id="latex" name="latex" class="textarea"
                placeholder="Paste or type your LaTeX here...">{{ text|e }}</textarea>

      <div class="form-actions">
        <button type="button" class="btn-secondary" id="copy-btn">Copy</button>
        <button type="submit" class="btn-primary">Check</button>
      </div>
    </form>
  </div>

  <!-- Highlighted panel -->
  <div class="panel">
    <div class="panel-header">
      <h2>Highlighted issues</h2>
      <span class="panel-tag panel-tag-secondary">Preview</span>
    </div>

    {% if highlighted %}
      <div class="code-view">{{ highlighted|safe }}</div>
    {% elif text %}
      <p class="placeholder">No issues found in the text 🎉</p>
    {% else %}
      <p class="placeholder">Run a check to see highlighted output here.</p>
    {% endif %}
  </div>
</section>
```

Issues list:

```html
<section class="issues-section">
  <h2>Issues</h2>

  {% if issues %}
    <ul class="issues-list">
      {% for issue in issues %}
        <li class="issue-item issue-item-{{ issue.kind }}">
          <span class="issue-badge issue-badge-{{ issue.kind }}">
            {{ issue.kind }}
          </span>
          <span class="issue-location">
            line {{ issue.line }}, col {{ issue.col }}
          </span>
          <code class="issue-char">'{{ issue.char }}'</code>
          <span class="issue-context">{{ issue.line_text }}</span>
        </li>
      {% endfor %}
    </ul>
  {% elif text %}
    <p class="no-issues">No issues to report. Nice work ✨</p>
  {% else %}
    <p class="no-issues">Paste some LaTeX above and click <strong>Check</strong> to see results.</p>
  {% endif %}
</section>
```

---

### 3.3 CodeMirror integration

To make editing easier, the textarea is enhanced by CodeMirror.

In `<head>`:

```html
<link rel="stylesheet"
      href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.13/codemirror.min.css">
<link rel="stylesheet"
      href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.13/theme/eclipse.min.css">
```

At the bottom of the document:

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.13/codemirror.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.13/mode/stex/stex.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.13/addon/edit/matchbrackets.min.js"></script>

<script>
  document.addEventListener('DOMContentLoaded', function () {
    const textarea = document.getElementById('latex');
    const copyBtn = document.getElementById('copy-btn');

    const cm = CodeMirror.fromTextArea(textarea, {
      mode: 'stex',
      lineNumbers: true,
      lineWrapping: true,
      matchBrackets: true,
      theme: 'eclipse',
      viewportMargin: Infinity
    });

    cm.setSize('100%', 'auto');

    // Copy button copies from CodeMirror
    if (copyBtn) {
      copyBtn.addEventListener('click', function () {
        const text = cm.getValue();
        if (!text) return;

        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).catch(console.error);
        } else {
          const temp = document.createElement('textarea');
          temp.value = text;
          document.body.appendChild(temp);
          temp.select();
          document.execCommand('copy');
          document.body.removeChild(temp);
          window.getSelection().removeAllRanges();
        }
      });
    }

    // Ensure textarea contains the latest content on form submit
    const form = document.querySelector('.checker-form');
    if (form) {
      form.addEventListener('submit', function () {
        textarea.value = cm.getValue();
      });
    }
  });
</script>
```

Result:

* LaTeX syntax highlighting,
* line numbers,
* wrapping,
* and a Copy button that works with the editor content.

---

### 3.4 CSS / layout (`static/style.css`)

Key parts:

* The two panels are laid out using flexbox:

  ```css
  .panels {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
  }

  .panel {
    flex: 1 1 340px;
    min-width: 0; /* crucial so panels don't force each other onto a new row */
    border-radius: 14px;
    border: 1px solid #e5e7eb;
    box-shadow: 0 12px 30px rgba(15, 23, 42, 0.08);
    background: #ffffffcc;
    backdrop-filter: blur(10px);
    padding: 16px 18px 18px;
  }
  ```

* The highlighted output (`.code-view`) and CodeMirror scroll areas allow horizontal scrolling for very long lines:

  ```css
  .CodeMirror-scroll {
    max-height: none;
    overflow-y: hidden;
    overflow-x: auto;
  }

  .code-view {
    margin-top: 0;
    padding: 6px 10px;
    background: #ffffff;
    border-radius: 10px;
    border: 1px solid #d1d5db;
    overflow-x: auto;
  }
  ```

* Issue highlighting classes:

  ```css
  .issue-digit    { background-color: rgba(248, 113, 113, 0.35); border-radius: 4px; }
  .issue-letter   { background-color: rgba(59, 130, 246, 0.35); border-radius: 4px; }
  .issue-punct    { background-color: rgba(251, 146, 60, 0.35); border-radius: 4px; }
  .issue-spacing  { background-color: rgba(147, 51, 234, 0.35); border-radius: 4px; }
  .issue-backslash{ background-color: rgba(16, 185, 129, 0.35); border-radius: 4px; }
  ```

* Issue list badges (small colored labels) use `.issue-badge-<kind>` classes to differentiate types.

---

## 4. Development and deployment

### 4.1 Local environment

* A conda environment is used (e.g. `latex-checker`):

  ```bash
  conda create -n latex-checker python=3.11
  conda activate latex-checker
  pip install flask
  ```

* Important: use `python app.py` (not `python3`) inside this env on Windows, so Flask is found in the correct environment.

### 4.2 Git & GitHub

Typical workflow in the project root (where `.git` lives):

```bash
git status
git add .
git commit -m "Describe the change"
git push
```

To ignore Python cache files:

```gitignore
__pycache__/
*.pyc
```

### 4.3 Render deployment

The app is deployed as a Render Web Service:

* Linked to the GitHub repo and a branch (usually `main`).
* Render builds from the repo and runs the Flask app.
* On the free tier, the service **sleeps** when idle.

  * First visit after sleep may take ~1–2 minutes as the service wakes.
  * Users should refresh after a short wait if they see a blank or loading state.

Every `git push` triggers a new deploy.

---

## 5. How to describe it to QA / other users

* This tool is meant as a **sanity check** for LaTeX transcription, *not* a perfect proof assistant.
* It currently reports:

  * digits outside math,
  * stray single letters outside math (except A/I),
  * top-level commas/colons in math (ignoring those inside `\{...\}`, `(...)`, `[...]`),
  * spacing problems around punctuation (space before, missing space after),
  * spaces just inside parens/quotes,
  * double backslashes `\\` anywhere.
* It’s based on your current understanding of the project’s style guidelines and can be extended as new patterns are identified.
* Hosted on Render’s free tier, so if the page doesn’t load immediately, wait a bit and refresh.

