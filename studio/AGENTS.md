# Studio Project - Agent Context

## Overview

Studio is a visual app builder for the Frappe Framework. It allows developers to build modern web applications using a drag & drop layout builder, wire Frappe Framework data sources, edit component props and slots, and create reactive apps with dynamic variables and scripts.

## Agent Guidelines & Code Conventions

1. **Guidelines for writing good code for a developer**
   - Choose clean code over clever code.
   - Write object oriented code as much as possible.
   - The size limits below are preferences, not quotas. Follow existing patterns and split code by responsibility.
   - Keep function sizes small, ideally 10 lines.
   - Write the main code/function first and write helper functions/building blocks below it in the order of usage.
   - Keep files small, upto 500 lines
   - Keep directories or module small, fewer than 15 files.
   - Reuse. Write as little code as possible.
   - If a fix needs a lot of complexity, explain why and look for a root cause or simpler approach before you continue.
   - Do not add a separate file, class, or helper for a few lines of code. Inline one-use helpers.
   - Keep each file to its own job. Do not let AI code, app mounting, or router code leak into unrelated files (for example `PageScript.vue` or the renderer).
   - Avoid side effects in constructors and at import time.
   - Don't add unnecessary dependencies unless required.
   - Don't narrate the code or explain the design in comments. Comment only non-obvious reasons, constraints, or compatibility decisions.
2. **Naming**
   - Avoid abbreviations, vague words (`contribution`, `bootstrap`), and prefixes that add no meaning.
   - Function names start with a verb and say what they do or return (`get_exported_docnames`, not `exported_names`).
   - Use the same name for a thing at every layer (Python, JS, CLI flag, template), for example `router_file`. Follow each language's casing.
   - Name files after what they hold. Rename a file when its job changes.
3. **Stay close to Vue and existing tools**
   - Use standard API as much as possible. Studio apps should render, route, and fail like a normal Vue app. Reuse the names and shapes of the library you wrap (for example `createRouter` options, and `extendRoute` from Vue Router's file-based routing).
   - If a fix belongs in frappe-ui or framework-ui, do not patch it in Studio. Suggest or make the fix in the respective project.
4. **Frontend Development:**
   - Rely on `frappe-ui` components (e.g., buttons, dialogs, inputs) instead of building them from scratch (local copy in ./frappe-ui/)
   - Use Tailwind CSS for styling. Avoid writing raw CSS (`.css` files or `<style>` blocks) unless absolutely necessary. Use espresso tokens only for colors and check dark mode after every UI change.
   - Use icon classes (`<span class="lucide-name">`) instead of importing icon components.
   - Match the existing editor UI as much as possible for adding new elements: subtle inputs, the same panel header height, small buttons, aligned labels and columns.
   - Generated boilerplate uses tabs, not spaces.
5. **Backend Development:**
   - Adhere to standard Frappe Framework conventions (Controller classes, hooks, `@frappe.whitelist()` methods).
   - Migrations and schema changes are handled via DocTypes.
   - Data patches must be idempotent. Scope text replacements to the fields that need them, not the whole serialized tree.
   - DB patches do not update exported page files on disk. When a data change affects them, migrate the files too.
6. **State Management & Reactivity:**
   - Use VueUse for common composition utilities.
   - Use Pinia for global state if needed, though most component states can be managed locally.
7. **Data Fetching**
   - Use `createResource`, `createDocumentResource`, `createListResource`, `call` from frappe-ui for data fetching
   - Look at ./src/data/ for examples of data fetching composables
   - Handle loading, error, and success states explicitly
8. **Tests**
   - One test class per Python module (`TestSync` for `sync.py`). Add new tests to it.
   - Write tests that cover real behaviour. Don't bloat the tests. Extend an existing test when you can.
9. **Writing and answering**
   - Write PR descriptions, issues, commit messages, help text, and docs in Simple Technical English (STE). Keep them short. Commit messages are a single line; add a body only when necessary.
   - Write user-facing help for a general Vue or frontend developer, not for someone who knows Studio internals.
   - Agent skill files must be lean. Add only what an agent cannot learn from the code.
   - When the user asks a question ("why", "should we", "just answer"), answer it. Do not change code until they ask.
   - When you check review comments, fix only real problems. Skip ones that are invalid or lead to overengineering, and say why.
