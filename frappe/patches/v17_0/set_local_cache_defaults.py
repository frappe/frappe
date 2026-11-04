import frappe

LOCAL_CACHE_DEFAULTS = {
	"max_cached_file_size": 100,
	"cache_keep_minutes": 300,
	"cache_grace_minutes": 60,
}


def execute():
	"""Existing sites hold no value for these settings, which read as 0."""
	for fieldname, value in LOCAL_CACHE_DEFAULTS.items():
		frappe.db.set_single_value("System Settings", fieldname, value)
