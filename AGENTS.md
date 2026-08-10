# frappe — Agent Instructions

Frappe framework. Python in `frappe/`; the Vue 3 + frappe-ui component library in `ui/`.

This file covers conventions that are easy to get wrong and expensive to undo. It is not a
style guide — formatting is handled by the pre-commit hooks in `.pre-commit-config.yaml`.

---

## Comments

**DO NOT ADD UNNECESSARY COMMENTS.** A comment earns its place only where the code cannot
speak for itself: a one-line note on what a file does, and a constraint a reader would
otherwise undo — a framework quirk, a build-time gotcha, a paint-order trap.

Three hard limits, so this stays a rule and not a judgement call:

- **Two lines maximum.** A comment that needs a third line is not a constraint, it is an
  explanation — put it in the commit message.
- **One summary line per docstring.** No rationale paragraphs, no "why not X", no examples.
  This applies to whitelisted endpoints too: document what it returns, not why it is built
  the way it is.
- **No commented-out code.** Delete it; git remembers.

Never narrate the next line, restate a name, explain a feature, or record history and
rationale. Watch for the phrase **"rather than"** — it is the signature of justifying your
choice against an alternative you did not take, and that belongs in the commit message.

Three things this rule does not cover, and which you should leave alone: the license headers
at the top of each file, the `# begin/end: auto-generated types` blocks in DocType
controllers, and generated scaffolding — `hooks.py` is mostly commented-out examples by
design, and the `.js` beside a new DocType controller ships as a commented-out stub. Those
are generator output, not somebody's explanation.

---

## Editing `ui/`

`ui/` is consumed by app repos through an aliased import (`@framework/ui` in crm). It ships
no Vitest config of its own — the tests under `ui/src/components/*/tests/` are run from a
host app, not from here. Assume a change to a component's public props, slots, or exports
is a change to somebody else's build.
