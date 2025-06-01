import nts
import nts.defaults
from nts.cache_manager import clear_defaults_cache
from nts.twofactor import PARENT_FOR_DEFAULTS
from nts.utils.password import encrypt

DOCTYPE = "DefaultValue"
OLD_PARENT = "__default"


def execute():
	table = nts.qb.DocType(DOCTYPE)

	# set parent for `*_otplogin`
	(
		nts.qb.update(table)
		.set(table.parent, PARENT_FOR_DEFAULTS)
		.where(table.parent == OLD_PARENT)
		.where(table.defkey.like("%_otplogin"))
	).run()

	# update records for `*_otpsecret`
	secrets = {
		key: value
		for key, value in nts.defaults.get_defaults_for(parent=OLD_PARENT).items()
		if key.endswith("_otpsecret")
	}

	if not secrets:
		return

	defvalue_cases = nts.qb.terms.Case()

	for key, value in secrets.items():
		defvalue_cases.when(table.defkey == key, encrypt(value))

	(
		nts.qb.update(table)
		.set(table.parent, PARENT_FOR_DEFAULTS)
		.set(table.defvalue, defvalue_cases)
		.where(table.parent == OLD_PARENT)
		.where(table.defkey.like("%_otpsecret"))
	).run()

	clear_defaults_cache()
