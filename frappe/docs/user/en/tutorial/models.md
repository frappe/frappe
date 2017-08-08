# Making Models

The next step is to create the models as we discussed in the introduction. In Frappé, models are called **DocTypes**. You can create new DocTypes from the Desk UI. **DocTypes** are made of fields called **DocField** and role based permissions are integrated into the models, these are called **DocPerms**.

When a DocType is saved, a new table is created in the database. This table is named as `tab[doctype]`.

When you create a **DocType** a new folder is created in the **Module** and a model JSON file and a controller template in Python are automatically created. When you update the DocType, the JSON model file is updated and whenever `bench migrate` is executed, it is synced with the database. This makes it easy to propagate schema changes and migrate.

### Developer Mode

To create models, you must set `developer_mode` as 1 in the `site_config.json` file located in /sites/library and execute command `bench clear-cache` or use the user menu in UI and click on "Reload" for the changes to take effect. You should now see the "Developer" app on your desk

	{
	 "db_name": "bcad64afbf",
	 "db_password": "v3qHDeVKvWVi7s97",
	 "developer_mode": 1
	}

{next}
