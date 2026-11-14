---
name: guided-implementation
description: Guide a new user through setting up the apps on this site, step by step, from what is already done to a first working transaction. Use when someone has just signed up, asks where to start, or wants help getting a module ready to use.
---

# Guided implementation

Help a new user get this site ready for real work. Each app ships its own
setup steps as Module Onboarding records, so follow those instead of
assuming what an app needs. Most users here are not developers: explain each
step in business terms, and do one step at a time.

## 1. See what is installed and what is done

Before asking anything:

- Read `Installed Applications` (its `installed_applications` rows give
  `app_name`, `has_setup_wizard` and `is_setup_complete`). If an app's setup
  wizard is not complete, start there.
- Read `System Settings` for language, time zone, currency, date and number
  format.
- Read `Module Onboarding` (`title`, `module`, `is_complete`) and, for each,
  its steps from `Onboarding Step` (`title`, `action`, `reference_document`,
  `reference_report`, `is_complete`, `is_skipped`, `description`). Skip
  modules the user's roles cannot open.

Then tell the user, in a few lines, which apps and modules are installed, what
is already set up, and what is left.

## 2. Ask what they need

Ask a few short questions, with `suggest_replies` for likely answers:

- what the business does, and what they want working first;
- which of the installed modules they will use now, and which can wait;
- how many people will use the site, and in what roles;
- whether they have data to bring in, such as customers, items, employees or
  opening balances.

Save the answers with `update_memory` so a later session can pick up from here.

## 3. Work through the onboarding steps

Take the modules the user chose, in a sensible order: organisation and master
data before transactions. For each open step, act on its `action`:

| Action | What to do |
| --- | --- |
| Create Entry | Explain the record, collect the values, show them, and `create` it after a yes. Read the doctype with `describe` first, so every mandatory field is covered. |
| Update Settings | Read the settings in `reference_document`, suggest values that fit the user's answers, and `update` after a yes. |
| View Report | Run `reference_report` with `run_report` and explain what it shows. |
| Show Form Tour, Go to Page, View Docs | Give the user the page or tour to open, with a one-line reason. |
| Complete Onboarding | Confirm the module is ready and summarise what was set up. |

A step can also be done in the UI by the user. Offer both, and accept either.
Skip a step the user does not need. After each step, check the result by
reading the record or settings back.

When a module has no onboarding steps, use the same order: its settings
doctype (find it with `find_doctypes`), then the master records its main
documents link to (follow the Link fields from `describe`), then one test
document.

## 4. Bring in existing data

For more than a handful of records, use Data Import rather than creating
records one by one:

1. Show which doctype to import first. Masters must exist before records
   that link to them.
2. Have the user download the template from Data Import and fill it in.
3. Import a small batch first, check it, then import the rest.

## 5. Users and roles

Add users only with the roles their work needs. Do not give everyone System
Manager. Explain what each role lets a person do.

## 6. Finish with a test run

Run one transaction through the main flow of each module the user chose,
using test data the user agrees to. Check the outcome together, such as the
document status, the ledger or stock it affected, and the matching report.
Then explain how to cancel or remove the test records, or suggest a test
company.

## Throughout

- Keep a short checklist of done and pending steps in your replies.
- Never create, update or submit anything without showing the values and
  getting a yes.
- Warn before choices that are hard to change after the first transaction:
  currency, chart of accounts, naming series, valuation method, fiscal
  year.
- Stop and point to an administrator if a step needs a role the user does not
  have.
