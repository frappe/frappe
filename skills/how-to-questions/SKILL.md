---
name: how-to-questions
description: Answer "how do I…" questions about this site and its apps with steps that fit how this site is set up, then offer to do it. Use when someone asks how to do, set up, change or find something.
---

# Answering how-to questions

Answer for this site, not for a generic install. Apps, settings, roles and
customisations change what the right steps are. Most people asking are not
developers: use the labels they see on screen, not field names or code.

## 1. Understand the goal

Work out what the user is trying to achieve, not only the words they used.
"How do I cancel an invoice" may really mean "how do I correct an invoice".
If two readings lead to different answers, ask one short question with
`suggest_replies` for the readings.

## 2. Check this site

Before answering:

- Find the doctypes involved with `find_doctypes`. Never guess a name.
- Use `describe` to confirm the fields, the user's permissions on them, and,
  for a record, the actions available on it.
- Read the settings doctype for the module (for example the module's
  Settings) when a setting changes the answer.
- Check that the needed app or module is installed. If it is not, say so.
- Check whether the user has the role to do it. If not, say who can.
- If knowledge bases are attached, search them with `search_knowledge` for
  this site's own guides and policies, and follow them.

## 3. Answer

Use this shape:

1. One line on what to do.
2. Numbered steps, with menu, button and field labels exactly as this site
   shows them.
3. Any prerequisite, such as a master record, a setting or a role.
4. A common mistake to avoid, if there is one.

Keep it short. Leave out options that do not apply on this site.

## 4. Offer to do it

When the tools can do it, offer to do it now or to make an example record.
Show the values first and act only after a yes. End with `suggest_replies`,
such as "Do it for me", "Show an example" or "Something else".

## 5. When it cannot be done

Say so plainly. Do not invent menus, fields or features. Suggest the closest
supported option, such as a custom field, a workflow, a report, a
notification or an app that adds it, and name who would need to set it up.
