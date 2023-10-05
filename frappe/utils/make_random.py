import random
from typing import TYPE_CHECKING

import frappe

if TYPE_CHECKING:
	from frappe.model.document import Document

settings = frappe._dict(
	prob={
		"default": {"make": 0.6, "qty": (1, 5)},
	}
)


def add_random_children(doc: "Document", fieldname: str, rows, randomize: dict, unique=None):
	nrows = rows
	if rows > 1:
		nrows = random.randrange(1, rows)

	for i in range(nrows):
		d = {}
		for key, val in randomize.items():
			if isinstance(val[0], str):
				d[key] = get_random(*val)
			else:
				d[key] = random.randrange(*val)

		if unique:
			if not doc.get(fieldname, {unique: d[unique]}):
				doc.append(fieldname, d)
		else:
			doc.append(fieldname, d)


def get_random(doctype: str, filters: dict = None, doc: bool = False):
	condition = []
	if filters:
		condition.extend(
			"{}='{}'".format(key, str(val).replace("'", "'")) for key, val in filters.items()
		)
	condition = " where " + " and ".join(condition) if condition else ""

	out = frappe.db.multisql(
		{
			"mariadb": """select name from `tab%s` %s
		order by RAND() limit 1 offset 0"""
			% (doctype, condition),
			"postgres": """select name from `tab%s` %s
		order by RANDOM() limit 1 offset 0"""
			% (doctype, condition),
		}
	)

	out = out and out[0][0] or None

	if doc and out:
		return frappe.get_doc(doctype, out)
	return out


def can_make(doctype: str) -> bool:
	"""Determine if it is possible to make a document of the given type.

	This function generates a random number and compares it to the probability
	of making a document of the given type. The probability is obtained from
	the 'settings.prob' dictionary using 'doctype' as key. If the random
	number is less than the probability, it returns True indicating that a
	document of the given type can be made. Otherwise, it returns False.

	Args:
		doctype (str): The type of document to be made.

	Returns:
		bool: True if it is possible to make a document of the given type, False otherwise.
	"""
	return random.random() < settings.prob.get(doctype, settings.prob["default"])["make"]


def how_many(doctype: str) -> int:
	"""Determine the number of documents that can be made of the given type.

	This function generates a random number within a range specified by the
	'settings.prob' dictionary using 'doctype' as key. The function returns
	the randomly generated number, which represents the number of documents
	that can be made of the given type.

	Args:
		doctype (str): The type of document.

	Returns:
		int: The number of documents that can be made of the given type.
	"""
	return random.randrange(*settings.prob.get(doctype, settings.prob["default"])["qty"])
