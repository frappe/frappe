from frappe.search.sqlite_search import _enqueue_index_job, get_search_classes


def execute():
	"""Rebuild search indexes that missed saves and deletes while another app's index was missing."""
	search_classes = get_search_classes()
	if len(search_classes) < 2:
		return

	for SearchClass in search_classes:
		search = SearchClass()
		if search.is_search_enabled() and search.index_exists():
			_enqueue_index_job(f"{SearchClass.__module__}.{SearchClass.__name__}")
