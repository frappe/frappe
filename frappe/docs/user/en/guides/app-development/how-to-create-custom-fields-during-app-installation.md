# How To Create Custom Fields During App Installation

Your custom app can automatically add **Custom Fields** to DocTypes outside of your app when it is installed to a new site.

To do this, add the new custom fields that your app requires, using the Frappé web application. 

In your `hooks.py` file, add `"Custom Fields"`

	fixtures = ["Custom Field"]

Export fixtures before you commit your app with:

	$ bench --site mysite export-fixtures

This will create a new folder called `fixtures` in your app folder and a `.csv` or `.json` file will be created with the definition of the custom fields you added.

This file will be automatically imported when the app is installed in a new site or updated via `bench update`.

Note: You can also add single DocTypes like "Website Settings" as fixtures


<!-- markdown -->
