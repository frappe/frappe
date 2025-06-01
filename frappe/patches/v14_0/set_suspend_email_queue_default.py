import nts
from nts.cache_manager import clear_defaults_cache


def execute():
	nts.db.set_default(
		"suspend_email_queue",
		nts.db.get_default("hold_queue", "Administrator") or 0,
		parent="__default",
	)

	nts.db.delete("DefaultValue", {"defkey": "hold_queue"})
	clear_defaults_cache()
