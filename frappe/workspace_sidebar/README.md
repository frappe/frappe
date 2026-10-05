# Frozen: the v16 sidebars, as the last v16 release shipped them

These files are no longer imported. A sidebar ships as `<module>/sidebar/` now.

They are kept, unchanged, so a site upgrading from v16 can tell its own edits from what the app
shipped: `frappe.patches.v16_0.carry_standard_sidebar_edits` compares each `Workspace Sidebar`
row on the site with the file of the same name here, and carries the difference into the site's
`Custom Sidebar`.

Do not edit, re-export or tidy them. A changed file reads as an edit on every site that never
made one. They go when the v16 conversion retires (see `frappe/desk/RETIRING.md`).
