from io import BytesIO

from babel.messages.extract import extract_python

from frappe.gettext.translate import PYTHON_KEYWORDS
from frappe.tests.utils import FrappeTestCase


class TestPython(FrappeTestCase):
	def test_extract_noop(self):
		messages = list(
			extract_python(
				BytesIO(b'N_("Created On")\n_lt("Last Updated On")'),
				keywords=PYTHON_KEYWORDS,
				comment_tags=(),
				options={},
			)
		)

		self.assertEqual(
			[(line, function, message) for line, function, message, _comments in messages],
			[(1, "N_", "Created On"), (2, "_lt", "Last Updated On")],
		)
