# Writing code in this repository

These are the standards for **desk v2 work** — `frontend/`, `ui/`, `frappe/shell/` and the
DocTypes those add. They are not a claim over the rest of `frappe`, whose code was written
under different conventions and is not swept to match.

Layer-specific rules live next to the layer and take precedence on their own ground:
[`frontend/PHILOSOPHY.md`](./frontend/PHILOSOPHY.md) (`DP1`-`DP4`),
[`ui/PHILOSOPHY.md`](./ui/PHILOSOPHY.md) (`FP1`-`FP3`), and the operational notes in
[`frontend/CLAUDE.md`](./frontend/CLAUDE.md) and [`ui/CLAUDE.md`](./ui/CLAUDE.md).

## Comments

**A comment earns its place only where the code cannot speak for itself**: a one-line note
on what the file does, and a constraint a reader would otherwise undo — a framework quirk,
a build-time gotcha, a paint-order trap.

Never narrate the next line, restate a name, explain a feature, or record history and
rationale. Three hard limits, so this stays a rule and not a judgement call:

- **Two lines maximum.** A third line means it is an explanation. Put it in the commit
  message.
- **One summary line per docstring.** No rationale paragraphs, no "why not X".
- **No commented-out code.**

Watch for the phrase **"rather than"**. It is the signature of justifying a choice against
an alternative you did not take, and that argument belongs in the commit message or the
ticket, not in the file.

A comment carries no ticket number. The constraint is the useful half; the citation ages
badly and sends the reader somewhere the code cannot follow.

**What this keeps.** A note like "freezing this instead of proxying it makes the object
non-extensible, so Vue's `reactive()` hands back the raw object and `meta` stops being
deeply reactive" is exactly the case for a comment: a reader would otherwise undo it. Cut
to the constraint and drop the history around it.

**Where a constraint is already written in a layer's `CLAUDE.md`**, the code does not
repeat it. One line naming the behaviour is enough.

## DocType field descriptions

A field's `description` is rendered as a paragraph under the input in the desk form, so it
is user-facing text. **One line, roughly 80 characters**, saying what the field holds and
any constraint on its value. Blank where the label already says it. The reasoning behind a
field's design belongs in its ticket.

## Shape

- Clean over clever. Object-oriented where the domain has objects.
- Functions small, around 10 lines. Main function first, helpers below it in call order.
- Files between 100 and 300 lines. Directories under 15 files.
- No abbreviations. Prefer a standard API to a hand-rolled one.
- Logic two pages share belongs in a module under `composables/` or `data/`, not in both.
- Build the minimum that works, then iterate. Add a dependency only when it is required.

## Before you close a ticket

Run `/quality-code-review`, and read your diff against the comment rule above. For a
change that is comments only, `.github/helper/comment_equivalence.py` proves it: it strips
comments from both revisions and asserts the remaining code is identical.

```bash
python .github/helper/comment_equivalence.py upstream/desk-v2 HEAD
python .github/helper/comment_equivalence.py --self-test
```

Two things it does not claim. It ignores blank lines and trailing whitespace **outside**
string literals, which cannot change behaviour in either language; inside a docstring or a
template literal both are content, and a change to either is reported. And it does not
prove a docstring *removal* is safe — a docstring is a runtime value in Python, so
anything reading `__doc__` changes behaviour. `--ignore-docstrings` compares the parsed
code with every docstring dropped, so the two revisions differ only in docstrings and
formatting; the test suites remain the proof that moving them was safe.
