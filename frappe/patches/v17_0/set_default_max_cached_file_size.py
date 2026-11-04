import frappe

DEFAULT_MAX_CACHED_FILE_SIZE_MB = 100


def execute():
	"""Existing sites hold no value for the new setting, which reads as 0 and caches nothing."""
	frappe.db.set_single_value("System Settings", "max_cached_file_size", DEFAULT_MAX_CACHED_FILE_SIZE_MB)
