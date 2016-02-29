# Adding to context

You can add more data for the pages by adding a `.py` file with the same filename (e.g. `index.py` for `index.md`) with a `get_context` method.

    def get_context(context):
        context.data = frappe.db.sql("some query")

{next}
