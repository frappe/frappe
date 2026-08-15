# Studio Project - Agent Context

## Overview

Studio is a visual app builder for the Frappe Framework. It allows developers to build modern web applications using a drag & drop layout builder, wire Frappe Framework data sources, edit component props and slots, and create reactive apps with dynamic variables and scripts.

## Agent Guidelines & Code Conventions

1. **Guidelines for writing good code for a developer**
   - Choose clean code over clever code.
   - Write object oriented code as much as possible.
   - Keep function sizes small, ideally 10 lines.
   - Write the main code/function first and write helper functions/building blocks below it in the order of usage.
   - Keep files small, between 100 and 300 lines
   - Keep directories or module small, fewer than 15 files.
   - Avoid abbreviations.
   - Use standard API as much as possible.
   - Reuse. Write as little code as possible.
   - Build the minimum working code, then iterate towards your goals.
   - Don't add unnecessary dependencies unless required.
   - DO NOT ADD UNNECESSARY COMMENTS for simple code. Use it only when the code is not self-explanatory.
2. **Frontend Development:**
   - Rely on `frappe-ui` components (e.g., buttons, dialogs, inputs) instead of building them from scratch (local copy in ./frappe-ui/)
   - Use Tailwind CSS for styling. Avoid writing raw CSS (`.css` files or `<style>` blocks) unless absolutely necessary. Use espresso tokens for styling
3. **Backend Development:**
   - Adhere to standard Frappe Framework conventions (Controller classes, hooks, `@frappe.whitelist()` methods).
   - Migrations and schema changes are handled via DocTypes.
4. **State Management & Reactivity:**
   - Use frappe-ui
   - Use VueUse for common composition utilities.
   - Use Pinia for global state if needed, though most component states can be managed locally.
5. **Data Fetching**
   - Use `createResource`, `createDocumentResource`, `createListResource`, `call` from frappe-ui for data fetching
   - Look at ./frontend/src/data/ for examples of data fetching composables
   - Handle loading, error, and success states explicitly
