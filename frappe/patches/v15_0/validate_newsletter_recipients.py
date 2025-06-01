import nts
from nts.utils import validate_email_address


def execute():
	for name, email in nts.get_all("Email Group Member", fields=["name", "email"], as_list=True):
		if not validate_email_address(email, throw=False):
			nts.db.set_value("Email Group Member", name, "unsubscribed", 1)
			nts.db.commit()
