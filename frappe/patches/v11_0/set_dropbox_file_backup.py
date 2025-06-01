import nts
from nts.utils import cint


def execute():
	nts.reload_doctype("Dropbox Settings")
	check_dropbox_enabled = cint(nts.db.get_single_value("Dropbox Settings", "enabled"))
	if check_dropbox_enabled == 1:
		nts.db.set_single_value("Dropbox Settings", "file_backup", 1)
