import nts
from nts.desk.utils import slug


def execute():
	for doctype in nts.get_all("DocType", ["name", "route"], dict(istable=0)):
		if not doctype.route:
			nts.db.set_value("DocType", doctype.name, "route", slug(doctype.name), update_modified=False)
