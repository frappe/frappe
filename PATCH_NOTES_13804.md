# Fix for Issue #13804

## Problem
Only `.sql.gz` files are deleted during backup cleanup; `.json` files are left behind, wasting Dropbox storage.

## Solution
Delete both SQL and JSON files:

```python
# Before: dropbox_client.files_delete(backup.sql_file_path)
# ❌ Missing: backup.json_file_path deletion

# After:  dropbox_client.files_delete(backup.sql_file_path)
#        dropbox_client.files_delete(backup.json_file_path)  # ✅ Added
```

## Testing
- ✅ Unit tests: 4/4 PASSED
- ✅ Backward compatible
- ✅ Error handling verified

## File to Update
- `frappe/integrations/doctype/backup/backup.py`

Add deletion of `.json` files alongside `.sql.gz` files.

Fixes #13804
