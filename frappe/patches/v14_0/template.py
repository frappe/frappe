from typing import List, Tuple

import click

# list of documents to reload with frappe.reload_doc
# example: ("core", "doctype", "doctype")
documents_to_reload: List[Tuple[str, str, str]] = [
	("core", "doctype", "doctype"),
]


def condition() -> bool:
	"""return value of this function determines whether patch will run or not.

	Patches are meant to repair data or change schema based on certain conditions, this function should capture them.

	Example:
	        A patch that should only execute if there are any Indian companies in database.

	        ```python
	        def condition:
	                return bool(frappe.db.exists("Company", {"country": "India"}))
	        ```

	Note:
	        1. This condition is ignored in patch tests.
	        2. If this function is removed from patch file, `execute` function is executed unconditionally.
	"""
	return True


def execute() -> None:
	click.secho(f"Executed patch {__file__}", fg="yellow")
