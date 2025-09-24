# Exporting Users from a Frappe Site (via REST)

This page shows a simple method to export `User` records via the REST API and save them as CSV.

## What the script does
- Calls `/api/resource/User` with selected fields.
- Supports API token auth or Basic Auth.
- Writes a CSV with columns: `name, email, first_name, last_name, enabled`.
  
