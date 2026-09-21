import textwrap
from io import BytesIO

from babel.messages.extract import extract, extract_python

from frappe.gettext.translate import PYTHON_KEYWORDS
from frappe.tests import UnitTestCase


class TestPython(UnitTestCase):
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

	def test_extract_context(self):
		code = textwrap.dedent(
			"""
			_("Anxious Anaximander", lang="de")
			_("With context", context="ctx")
			_("Positional", "de", "greeting")
			_lt("Lazy", context="lazyctx")
			_(
				"Multi line",
				context="multictx")
			_("Dup") if flag else _("Dup", context="dupctx")
			_("First", context="firstctx") + _("Second")
		"""
		)
		messages = extract(
			"frappe.gettext.extractors.python.extract", BytesIO(code.encode()), keywords=PYTHON_KEYWORDS
		)

		self.assertEqual(
			[(line, message, context) for line, message, _comments, context in messages],
			[
				(2, "Anxious Anaximander", None),
				(3, "With context", "ctx"),
				(4, "Positional", "greeting"),
				(5, "Lazy", "lazyctx"),
				(6, "Multi line", "multictx"),
				(9, "Dup", None),
				(9, "Dup", "dupctx"),
				(10, "First", "firstctx"),
				(10, "Second", None),
			],
		)
