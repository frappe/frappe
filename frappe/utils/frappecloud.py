import nts

nts_CLOUD_DOMAINS = ("nts.cloud", "erpnext.com", "ntshr.com", "nts.dev")


def on_ntscloud() -> bool:
	"""Returns true if running on nts Cloud.


	Useful for modifying few features for better UX."""
	return nts.local.site.endswith(nts_CLOUD_DOMAINS)
