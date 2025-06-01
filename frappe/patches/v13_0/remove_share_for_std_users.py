import nts
import nts.share


def execute():
	for user in nts.STANDARD_USERS:
		nts.share.remove("User", user, user)
