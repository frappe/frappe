# Adding Module Icons On Desktop

To create a module icon for a Page, List or Module, you will have to edit the `config/desktop.py` file in your app.

In this file you will have to write the `get_data` method that will return a dict object with the module icon parameters

### Example 1: Module Icon

	def get_data():
		return {
			"Accounts": {
				"color": "#3498db",
				"icon": "octicon octicon-repo",
				"type": "module"
			},
		}

### Example 2: List Icon

	def get_data():
		return {
			"To Do": {
				"color": "#f1c40f",
				"icon": "fa fa-check",
				"icon": "octicon octicon-check",
				"label": _("To Do"),
				"link": "List/ToDo",
				"doctype": "ToDo",
				"type": "list"
			},
		}


Note: Module views are visible based on permissions.

<!-- markdown -->