If you want to add **Custom Fields** to your app so that they are automatically created when you app is installed on a new site, you will have to add them as **Fixtures** in the `hooks.py` file of your app.

In your `hooks.py` file, add `"Custom Fields"`

	fixtures = ["Custom Field"]

Export fixtures before you commit your app with:

	$ bench --site mysite export-fixtures

This will create a new folder called `fixtures` in your app folder and a `.csv` or `.json` file will be created with the custom fields.

This file will be automatically imported when the app is installed in a new site or updated via `bench update`.

Note: You can also add single DocTypes like "Website Settings" as fixtures


<!-- markdown -->