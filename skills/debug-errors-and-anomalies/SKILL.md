---
name: debug-errors-and-anomalies
description: Find the cause of an error message, a failed background job or email, or numbers that look wrong on this site, and explain the fix in plain language. Use when a user reports something broken, failing or not adding up.
---

# Debugging errors and anomalies

Most people reporting a problem are not developers. Find the cause on this
site, then explain it in business language: what happened, why, and what to
do. Investigate with read tools only; change nothing until the user agrees to
a fix.

## 1. Pin down the symptom

Before searching, know:

- the exact message, or what they expected against what they see;
- the document, page or report, with its name if they have it;
- roughly when it happened, and as which user;
- whether it happens every time, or only for some records or users.

If the report is just "it's broken", ask for these in one short question.

## 2. Gather evidence

Use `read_records`, `describe` and `run_report`. Filter by time and by
reference first, since logs on a busy site are large.

| Look in | Filter on | Tells you |
| --- | --- | --- |
| `Error Log` | `creation` near the time, `method`, `reference_doctype`, `reference_name` | the traceback behind a server error |
| `Scheduled Job Log` | `status: Failed`, `scheduled_job_type` | scheduled jobs that failed, with `details` |
| `RQ Job` | `status: failed`, `job_name` | background jobs that failed, with `exc_info` |
| `Email Queue` | `status: Error`, `reference_doctype`, `reference_name` | emails that did not go out, with `error` |
| `Integration Request` | `status: Failed`, `reference_doctype` | calls to payment gateways and other services |
| `Version` | `ref_doctype`, `docname` | who changed a record, and what changed |

For a record, `describe(doctype, name)` gives its state and the actions the
user can take on it. Read the record itself for the values involved.

## 3. Match the cause

| Symptom | Usual cause | Check |
| --- | --- | --- |
| "Not permitted", "Insufficient Permission" | Role or user permission missing | `describe` on the doctype; the user's roles and User Permission rows |
| "Mandatory fields required", "Value missing" | A required field is empty, often one hidden by a condition | the field in `describe` and its value on the record |
| "Could not find …", invalid link | Linked record missing, renamed or disabled | read the linked doctype for that name |
| "Duplicate entry", "already exists" | Name or unique field already used | naming series and the existing record |
| "Cannot edit cancelled document", "not submitted" | Record is in the wrong state | `docstatus` and `status` on the record |
| Error that names a Server Script or Client Script | Site customisation throwing | read the `Server Script` or `Client Script` |
| Scheduled work not happening | Scheduler disabled or job failing | `enable_scheduler` in `System Settings`; `Scheduled Job Log` |
| Emails not received | Email account or outgoing server failing | `Email Queue` errors; the `Email Account` |
| Timeouts, "request timed out" | Too much data in one request | the record or report size; suggest filters or a background job |
| Traceback inside app code with valid data | A bug in an app | stop and escalate (see step 6) |

## 4. Numbers that look wrong

When a total, balance or stock figure does not match what the user expects:

1. Write down both numbers: what they expect and what the site shows, with
   the report or document and the filters used.
2. Trace the figure back to its source records with `run_report` or
   `read_records`, keeping the same filters.
3. Check the usual reasons for a gap:
   - drafts or cancelled documents counted, or left out;
   - posting date outside the period, or backdated entries;
   - a different company, branch, warehouse or cost centre;
   - currency and exchange rate differences;
   - rounding and tax inclusion;
   - duplicate records, or a return or credit note not linked to the original.
4. Show the rows that explain the gap, so the user can see the cause, not
   only hear it.

## 5. Report back

Answer in this shape:

- **What happened:** one or two sentences in the user's terms.
- **Why:** the cause, with the record, log or setting that proves it.
- **How to fix it:** numbered steps the user can follow in the UI.
- **Who needs to act:** the user, an administrator, or a developer.

Then offer to make the fix if you can, and end with `suggest_replies`.

## 6. Guardrails

- Stay read-only while investigating. Get a clear yes before any `create`,
  `update` or `run_action`.
- Never fix a permission error by granting a role, and never weaken a
  permission or setting to make an error go away. Point the user to an
  administrator.
- Never delete logs, and never cancel or amend a submitted record without
  approval.
- When a traceback points into app code and the data is valid, do not patch
  data around it. Summarise the traceback, the steps to reproduce and the
  record, and suggest raising it with the app's developers or support.
