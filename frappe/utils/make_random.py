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

	for _ in range(nrows):
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


def get_random(doctype: str, filters: dict | None = None, doc: bool = False):
	condition = []
	if filters:
		condition.extend("{}='{}'".format(key, str(val).replace("'", "'")) for key, val in filters.items())
	condition = " where " + " and ".join(condition) if condition else ""

	out = frappe.db.multisql(
		{
			"mariadb": f"""select name from `tab{doctype}` {condition}
		order by RAND() limit 1 offset 0""",
			"postgres": f"""select name from `tab{doctype}` {condition}
		order by RANDOM() limit 1 offset 0""",
			"sqlite": f"""select name from `tab{doctype}` {condition}
		order by RANDOM() limit 1 offset 0""",
		}
	)

	out = (out and out[0][0]) or None

	if doc and out:
		return frappe.get_doc(doctype, out)
	return out


def can_make(doctype: str) -> bool:
	return random.random() < settings.prob.get(doctype, settings.prob["default"])["make"]


def how_many(doctype: str) -> int:
	return random.randrange(*settings.prob.get(doctype, settings.prob["default"])["qty"])
