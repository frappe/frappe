# frappe/frontend — Design Philosophy

This is the rulebook that governs the desk layer: the shell, the record page, and
everything an app customizes them with. Every principle is **generative** — applying it
gives you the right answer in situations it doesn't explicitly cover. When two principles
tug in opposite directions, the principle text usually points at the tiebreaker.

**Audience:** contributors, AI agents doing PRs, reviewers. Not end users.

**How to use it:**

- Cite by ID in PRs and issues (`"this violates DP1"`, `"DP3 — read the script an author
  would write"`).
- When you draft a new module or refactor an old one, walk this doc top-to-bottom.
- When a principle stops being generative — when it forces a clearly wrong answer in a
  real case — propose an edit, don't carve a quiet exception.

## What this doc inherits, and does not restate

`frappe/frontend` sits downstream of two libraries and inherits both rulebooks in full:

- **`frappe-ui` (`P1`–`P14`)** — naming, `v-model`, primitive props, color axes, labeling,
  slot vocabulary, splitting, styling via `data-*`, icons, a11y, deprecation. Canonical
  source: **[frappe-ui's `PHILOSOPHY.md`](https://github.com/frappe/frappe-ui/blob/main/PHILOSOPHY.md)**,
  linked rather than pathed because `frappe-ui` is a peer dependency each app vendors at a
  different location.
- **`@framework/ui` (`FP1`–`FP3`)** — compose atoms don't rebuild them, controlled
  components with host-owned persistence, options derived from doctype Meta. See
  [`../ui/PHILOSOPHY.md`](../ui/PHILOSOPHY.md).

Neither is repeated here. Two divergent copies of a rule is exactly the drift these rules
exist to prevent. This doc adds only the `DP*` principles specific to the desk layer.

## Relationship to other docs

- **`CLAUDE.md`** is *operational* — the traps, the formatting, the commands. The design
  rules live here, not there.
- **`CONTEXT.md`** is the *vocabulary* — what a **Record page**, a **contribution**, a
  **surface**, a **Page Script** mean. PHILOSOPHY is the *rules* that use the vocabulary.
  Not yet written.
- **`docs/adr/`** are *decisions* — specific applications of a principle to a specific
  question. **ADRs cite principles; principles never cite ADRs.** That direction is what
  stops this file growing a paragraph every time something is settled. Not yet written.
- **The wayfinder maps** (frappe/frappe#42061 and its children) hold **charter points**.
  A charter point is map-scoped and expires when its map wraps; a principle is what
  survives the wrap. See below.

## How a principle gets here

This file is **harvested, not authored**. Sitting down to invent ten principles produces
ten plausible sentences, four of which turn out wrong and three of which were never
load-bearing. Every `DP` below is a rule that was already fought over.

A candidate earns a slot only if it passes all four:

1. **Generative.** It answers cases it does not mention. If it only answers the case that
   prompted it, it is an ADR.
2. **It has a real counter-pull.** The text must name what tugs the other way. A rule
   nobody could plausibly violate is decoration, and decoration is not free — it pads the
   file until the load-bearing rules stop being read.
3. **Not inherited.** It is not already `P1`–`P14` or `FP1`–`FP3` in different words.
4. **Earned.** Somebody got it wrong at least once, or two independent decisions leaned
   on it.

**The admission gate: a map's charter point graduates into a principle when a second map
inherits it.** One map needing a rule proves only that the rule fit one destination. Two
maps arriving at it independently is the evidence that it generalizes. Until then it
stays in the charter, where it can expire.

Deliberately strict. Most charter points will never graduate, and that is the point.

---

## DP1. Classify by who a thing serves, not by what it imports

**Rule:** A module belongs in `frappe/frontend` when it has **one correct way to be used**
and speaks doctype/page/script vocabulary. It belongs in `@framework/ui` when an app could
reasonably use it however it liked. Ask who the thing serves — never where its imports
point.

`@framework/ui` keeps what the desk layer merely *consumes*: `components/FormLayout`,
`components/Fields`, and the `useDocPermissions` / `useUserRoles` / `useDoctypeMeta`
composables. The record-page engine, `PanelLayout` and the Page Script editor are desk
layer and live here.

**Why:** The trap is that a desk-layer module's imports point *into* the generic library,
and that reads like a co-location argument for moving it there. It is the opposite:
**consuming generic components is what makes something the desk layer.** `PanelLayout`
looks generic until you read its props — `surface: Surface<PanelSectionItem>` and `page`,
straight from the engine. A Page Script editor is the customization layer by definition.

The counter-pull is real: a thing in `@framework/ui` is reachable by any app immediately,
and moving it later costs a deprecation cycle. Take that trade only when the thing passes
the test above, not because a second app happens to want it today — an app wanting it is
an argument for extracting the *generic part* it needs, not for relocating the whole.

---

## DP2. The customization path is the build path

**Rule:** The doors an app uses to customize the desk are the same doors the framework's
own features go through. When you add a capability, the framework's use of it must not be
special-cased, privileged, or wired ahead of the contribution mechanism. If the framework
needs a back door to build its own feature, the front door is not finished.

**Why:** This is the root map's destination, stated as a rule. Desk v1 grew customization
as an afterthought — Client Script, Property Setter and Customize Form bolted onto a UI
that was never designed to be extended — and the result is a tier apps route *around*
rather than through. An optional customization API is one that rots, because the
framework's own pressure never lands on it.

The tell that this is holding: `frontend/src/contributions/registry.ts` is tiny, and its
size is the argument. Its own comment says so. The tell that it is slipping is a growing
list of things the framework can do that a contribution cannot name.

---

## DP3. Judge the API by reading what an author would write

**Rule:** Before settling any customization API, write out the artifact a real author
would author against it — the Page Script, the `hooks.py` entry, the seeded rows, the
`record.js`. Judge the design from that artifact, not from the type signature or the
implementation. If the authored form reads badly, the API is wrong however clean the
internals are.

**Why:** The authored artifact is the only surface an app developer ever sees; everything
else is ours. This is the rule that produced maps 1-4, and it has repeatedly caught
designs that were internally elegant and unusable from outside.

The counter-pull is that writing the sample costs a real hour before any code exists, and
it always feels like the obvious next step is to build the thing instead. Pay the hour.

---

## DP4. A contribution adds; it never edits a shared thing

**Rule:** An app extends the desk by contributing a **new, colocated, additively-merged**
row, file or module — never by editing a value another app also owns. When a design offers
a shared list, a shared field or a single scalar slot that two apps would both want to
set, that is the signal to make it a set of rows keyed by owner instead.

**Why:** Anything two apps must both write becomes a thing they fight over, and the loser
is decided by load order — silently. A `Select`'s options live in one DocType JSON owned
by one app, so a second app can only extend it with a Property Setter, which is
customization-as-extension and exactly the v1 pattern desk v2 exists to replace. Link rows
are additive with no shared field to contend for. Colocation carries ownership without a
registry lookup: a file in the owner's own tree *is* the owner's.

The counter-pull is that a scalar is genuinely simpler, and for a value only one app can
sensibly own it is the right call. The test is not "is it simpler" but "could a second app
reasonably want to set this too" — and on a framework where any app can install alongside
any other, that answer is yes far more often than it first looks.
