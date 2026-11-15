from frappe.desk.widgets import WidgetType


class QuickList(WidgetType):
	"""A short list of a DocType's records. The base class checks the reader may read the DocType;
	rows load in the browser, where each DocType's list view settings draw their badges."""
