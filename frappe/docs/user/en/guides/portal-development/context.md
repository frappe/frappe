# Dynamic Pages

You can render pages dynamically using Jinja templating language. To query data, you can update that `context` object that you pass to the template.

This can be done by adding a `.py` file with the same filename (e.g. `index.py` for `index.md`) with a `get_context` method.

### Example

If you want to show a page to see users, make a `users.html` and `users.py` file in the `www/` folder.

In `users.py`:

	import frappe
    def get_context(context):
        context.users = frappe.db.sql("select first_name, last_name from `tabUser`")

In `users.html`:

	<h3>List of Users</h3>
	<ol>
	{% for user in users %}
		<li>{{ user.first_name }} {{ user.last_name or "" }}</li>
	{% endfor %}
	</ol>

{next}
