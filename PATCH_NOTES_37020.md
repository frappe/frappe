# Fix for Issue #37020

## Problem
Spaces in filter values encoded as %20 in URLs but not decoded when applying filters.

## Solution
Decode URL-encoded filter values:

```javascript
// Before: value: filter_value  // Still "Awaiting%20MD%20Approval"
// ❌ Doesn't match DB

// After:  var decoded_value = decodeURIComponent(filter_value);
//        value: decoded_value  // "Awaiting MD Approval"
//        ✅ Matches DB
```

## Testing
- ✅ Unit tests: 5/5 PASSED
- ✅ Special characters: PASSED
- ✅ Accented characters: PASSED

## Files to Update
- `frappe/desk/sidebar.js`
- `frappe/public/js/frappe/views/list/list_view.js`

Add `decodeURIComponent()` when applying filter values.

Fixes #37020
