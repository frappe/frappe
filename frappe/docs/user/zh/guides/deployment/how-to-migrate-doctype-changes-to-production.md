# How To Migrate Doctype Changes To Production

#### 1. DocType / Schema Changes

If you are in `developer_mode`, the `.json` files for each **DocType** are automatically updated.

When you update in your production using `--latest` or `bench update`, these changes are updated in the site's schema too!

#### 2. Permissions

Permissions do not get updated because the user may have changed them. To update permissions, you can add a new patch in the `patches.txt` of your app.

	execute:frappe.permissions.reset_perms("[docype]")

<!-- markdown -->