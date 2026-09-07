---
name: review-like-ankush
description: >-
  Review a PR/diff the way Ankush actually does it on GitHub — the concrete,
  mechanical reflexes and the review-comment voice, distilled from ~1,500 of his
  real frappe/frappe and frappe/erpnext review comments. Use this when reviewing
  an actual diff or PR in Frappe/ERPNext (or Frappe-style Python/JS) and you want
  the specific checks he flags on sight plus how he phrases the comment. For the
  underlying principles (the "why"), pair with the quality-code-review skill.
---

# Review like Ankush

This is the **field manual** version of a review — what Ankush actually types on
PRs, in the order he prioritizes it, in his voice. It is grounded in his real
review comments, not essays. (For the principles behind these reflexes — the
"why it matters" — see the sibling skill `quality-code-review`.)

## How he triages a diff

He reviews in a fixed order of consequence, and what he *blocks* on vs *nits* on
is consistent:

1. **Correctness / logic** — does it actually do the right thing, including the
   second-order cases the author didn't think about? **Blocks.**
2. **Performance** — N+1, caching, indexes, full-table scans, work-in-loops.
   Treated as correctness, not polish. **Blocks at scale.**
3. **Security & framework safety** — permissions, raw SQL, multi-tenancy,
   validation bypass. **Blocks.**
4. **Backward compatibility & migrations** — breaking signatures, schema changes
   needing patches. **Blocks.**
5. **Simplification & reuse** — too much code, duplication, reinvented utility.
   Strong push, usually blocks if egregious.
6. **Tests** — coverage for the new behavior and its transitions. **Blocks** on
   critical/permissions/stateful changes; "up to you" otherwise.
7. **Naming, readability, messages, style, i18n** — nits; called out but rarely
   blocking unless intent is unclear.

> Don't rubber-stamp. The signature move is to ask **"Why?"** — force the author
> to justify the change before it lands.

---

## 1. Correctness & logic (block)

Read for the case the author *didn't* test. He reasons through domain
second-order effects, not just the diff in isolation.

- **Trace the unhappy/edge path.** "This does _nothing_ on cancellation 😄";
  "This still means same serial no can be sold twice if not reserved";
  "You're double counting invoices where `project` is set on parent and children
  both."
- **Check the types in a condition actually match.** "This condition will almost
  never be true? Because `to_time` will be string and `add_to_date` returns
  datetime object." Casting reflex: "This should be casted to integer, else it's
  always true."
- **Question the return shape.** "The shape of return could be `[None, None]` if
  not found? 🤔" Watch `db.get_value(..., as_dict=1)` (list) vs scalar.
- **Never mutate a list/child-table while iterating it** — "Removing items from
  the list while iterating over it can lead to RuntimeError." Reset index / build
  a new list / iterate `reversed()`.
- **Mutable default args** — `items=[]`/`rules={}` → `=None` with a guard.
- **A no-op test is a bug.** "This code is no-op. unittest will fail on first
  assertion failure." Prefer `assertRaises(...)` to manual try/except.
- **Don't silently change long-standing semantics.** "You can't just change
  semantics that have been in place for a long time like this."

## 2. Performance (block at scale — "don't make it slower in the first place")

This is the single densest category in his reviews. Scan every loop and every
page-load path.

- **DB call in a loop → flag it.** `frappe.db.get_value` / `get_doc` /
  `db.sql` inside `for` is the #1 reflex. Fixes, in order of preference:
  - add `cache=True`: "This will probably get called 100s of time in same DB
    transaction. Better to cache the results." (`db.get_value(..., cache=True)`)
  - hoist out of the loop / do it once per parent: "This can be done once per SO
    instead of once per item."
  - bulk-fetch with `get_list(..., pluck=...)` and look up in a dict.
- **Don't fetch a whole doc for one value.** "avoid getting whole doc just for
  single value. `get_single_value` or `get_value` should be used... `get_doc` is
  bad for performance." `db.set_value` over `get_doc().save()` for a single
  column. `frappe.delete_doc(...)` over `get_doc().delete()` (the latter fetches
  the doc that's about to be nuked).
- **Reorder conditionals so the DB call is last** — short-circuiting skips it:
  "Re-order conditional so DB call is last."
- **Unindexed filter = full scan.** "Owner by default isn't indexed, so this is
  2x slow queries." Name forced indexes explicitly. Never read a MyISAM table in
  a hot path ("implicit global locking and should never be used like this").
- **Push aggregation into SQL.** "why are we fetching all SLE to sum them up in
  python, we can just sum them up in SQL also 😬." Add the condition to the
  subquery so filtering happens before the join.
- **`not in <list>` in a loop** grows O(n²) → use a `set`.
- **Watch what runs on every page load / every few seconds.** "just keeping that
  page open would bring the site down because it was serializing all jobs every
  5 seconds." Long jobs → `enqueue(..., queue="long")`.
- **Caching nuance:** redis cache doesn't work with filters — "It's better to do
  `db.get_value(cache=True)` here because redis cache doesn't work with filters."
  `@request_cache` is often the right, simpler scope. Don't hand-roll cache
  serialization — `cache.set_value/get_value` (multitenancy-safe) over `.set/.get`.

## 3. Security & framework safety (block)

- **Raw queries don't respect permissions or multitenancy.** "If possible lets
  use `frappe.get_list` instead of raw query. Raw query wont respect permission
  rules that site might have configured." Use the ORM specifically so per-site
  perms apply: "Use ORM, so if user has write to add this role then only they'll
  be able to do it."
- **Never f-string into SQL.** "Why f-string here?" Use `frappe.qb` or `%s`
  params. (Also: new raw SQL is discouraged outright — "We are trying to make
  ERPNext db agnostic" / Postgres support.)
- **Validation bypass is dangerous.** "Ignoring validation is VERY dangerous. It
  also ignores running the `validate` method that does a lot of preprocessing."
  Question every `ignore_validate` / `ignore_permissions=True`.
- **Whitelisted methods are reachable by low-privilege/website users by default**
  — they need explicit permission checks, `methods=[...]` on security-critical
  endpoints, and search endpoints must honor `txt`/`start`/`page_len`.
- **Don't hardcode roles/permissions in logic.** "We do not hardcode roles like
  this in code. Only Submit permission should be checked IMO."
- **XSS framing:** storing data isn't the risk — "using it incorrectly by
  injecting it as HTML inside the DOM is." Use `get` requests over `frappe.call`
  where there should be no side effects ("Safer IMO").

## 4. Backward compatibility & migrations (block)

- **New args go last and are kwargs with defaults.** "New keyword arguments
  should be preferably added to the end to avoid breaking non-kwarg function
  calls. Also `None` is a better default than an empty string."
- **Don't remove/rename public functions** without a back-compat shim:
  `def old_name(...): return new_name(...)`. "avoid renaming public function 😅";
  "There might be someone using this as its public functionality." Bench
  especially: "Bench has to be backward and forward compatible."
- **Schema changes need a patch.** "These new fields won't get auto patched.
  You'll have to write patch to migrate existing data." Type changes (text→int)
  need a migration. Singles don't sync defaults to existing sites — patch them.
- **Patch hygiene:** patches must be **idempotent** ("If this patch is retried
  everything will become 0 😄"); ordered correctly (a patch reading a new field
  must run after the field exists, and not in the post-sync phase if it's already
  reloaded); and live in the right app (a framework-added validation gets patched
  in framework, not ERPNext). `reload_doc` is often unnecessary now — "We use
  hash-based migration now."
- **Modifying an existing test to make it pass is a red flag** — "it is indeed
  breaking an existing workflow."

## 5. Simplification & reuse (push hard)

- **"Why this much code?"** is a recurring opener. "Why this much code for
  setting default? Just edit child table doctype and put `0.0` as default value.";
  "This method can be removed entirely."
- **Reuse the existing utility.** "get_descendants does exactly this.";
  "Import this function instead of manually splitting it." Manual `serial_no`
  string handling especially — "Every manually handling of [serial_no] has
  resulted in bugs in past."
- **Prefer the boring construct.** "One liners with and/or for chaining are
  needlessly confusing. Can you write a normal function instead?";
  "map/lambda unnecessary" → list/generator comprehension.
- **Guard clauses over nesting.** "Always use guard conditions to avoid over
  indenting." Merge nested `if`s.
- **Don't over-abstract.** "This is supposed to be a fairly simple problem to
  solve, it doesn't need so much inheritance/abstractions/indirections." Don't
  pull millions of lines of dependency (pandas) for a 10-line loop.
- **Closures are for reading, not writing** — "Just return the document and
  operate on it instead."
- **Commented-out / dead code never gets merged.** "Commenting out code is never
  required. Feel free to delete stuff that's not required."
- **Split unrelated changes.** "this seems unrelated. Split commits/PR?" Revert
  cleanly for good `git blame`.

## 6. Tests (block on the risky stuff)

- **Demand a test for the new behavior and its transitions** — especially
  critical/permissions/stateful changes: "This is critical change from
  permissions POV, it should have multiple tests for validating it works." For
  smaller things it's "up to you: Add a test case for this behaviour. (just
  encode the steps you described in a unit test 😄)."
- **Tests must be deterministic & independent.** No `random` ("Better to avoid
  random behaviour in tests"); no cross-test state ("tests should never have
  dependencies on any other tests"); use `freeze_time` for time.
- **Mechanical:** test methods must start with `test_` ("This test won't run");
  the second arg to `assertX`/`db.exists` is a failure message, not data.
- Write tests **progressively with the change**, not at the end — "That step
  usually gets skipped when deadlines are near."

## 7. Naming, messages, i18n, style (nit, but say it)

- **Names must reveal intent.** A `get_*` function must not mutate state. "`sno`
  is bad variable name; `sr_no` maybe?" Pass the real fieldname into shared
  utilities instead of guessing (`fieldname + "_item"`). Prefix internal helpers
  in `utils/*` with `_`.
- **User-facing messages:** specific, crisp, no programmer-speak. "Replace
  'string' with text, string is programmer-talk."; "We almost never need to use
  exclamation mark in user facing messages."; "No need to write `kindly`."
- **i18n:** wrap user-facing strings in `_()`; **string formatting goes *after*
  the `_()` call**, never an f-string inside it:
  `_("Item {0} does not exist").format(code)` ✅, `_(f"... {code}")` ❌. Don't
  translate non-user-facing/business-logic strings at all. (JS uses `__()`.)
- **Style is CI's job.** "Use isort/precommit 😄"; tabs not spaces; don't relitigate
  formatting by hand — but do flag genuinely confusing layout.

---

## His voice — how to write the comment

Match this register when producing review output:

- **Lead with a question, not a verdict.** "Why?", "Any particular reason
  for...?", "Intentional?", "Does this work? 🤔" — make the author justify it.
- **State problems as fact, briefly.** "This is likely a bug.", "This isn't
  correct.", "Not required.", "This seems unrelated." No hedging, no padding,
  rarely "please."
- **Always offer the better path.** Pair the critique with a concrete
  alternative or a ```suggestion block — never just "wrong."
- **Soften with humor, not qualifiers.** Sparing emoji (😄 😅 🤔 😬 🤦) carry the
  friendliness; the words stay direct.
- **Explain the *why* when you block** — what breaks, for whom, at what scale.
- **Signal confidence level honestly.** "IMO", "up to you" = genuinely optional;
  no qualifier = he means it. Admit uncertainty ("not sure about alternate impl
  yet but this is gonna become a problem") and change your mind if the author has
  better reasoning.
- **Approve warmly and briefly.** "LGTM 👍", "Rest LGTM", "everything else mostly
  looks good 👍".
- **Process check:** critical changes (caching, DB APIs, permissions) need a
  second reviewer even if you *can* self-merge — "you should at least get approval
  for critical PRs."

## Frappe API cheat-sheet (preferred → flagged)

- `frappe.get_list/get_all` (respects perms) **over** raw SQL; `frappe.qb` for
  complex queries **over** `db.sql` string-building.
- `db.get_value(..., cache=True)` / `get_cached_value` / `get_cached_doc` for
  repeated reads; `@request_cache` for request scope.
- `db.get_value` / `db.get_single_value` / `db.set_value` for single values
  **over** `get_doc().save()`; `frappe.delete_doc` **over** `get_doc().delete()`.
- `.get(field)` **over** `getattr(doc, field)`; `.run(pluck=...)` **over** list
  comprehension on results; `as_dict=True` **over** positional result indexing.
- `frappe.call()` **over** `frappe.get_attr(hook)()` (keeps hooks extensible);
  named kwargs **over** 5 positional args.
- `cache.set_value/get_value` (multitenant, auto-serialize) **over** `.set/.get`.
- `frappe.local` **over** `frappe.flags` for request-scoped state.
- DB-level unique constraint (`db.add_unique`) **over** code-only validation for
  integrity.
- `cint/flt/cstr` **over** `int/float/str`; don't compare checkbox fields to
  `"1"`. `get_meta("X").get_options("status")` **over** hardcoded option lists.
- Reference/computed fields: set `no_copy: 1`, `read_only: 1`, `print_hide: 1`.

---

### Source

Distilled from ~1,533 of Ankush's real inline review comments and review
summaries on `frappe/frappe` and `frappe/erpnext` (1,000 reviewed PRs sampled via
the GitHub API). Quotes are verbatim. Complements `quality-code-review` (same
reviewer, derived from his engineering essays).
