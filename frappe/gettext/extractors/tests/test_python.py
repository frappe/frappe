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
				context="multictx",
			)
			_("Dup") if flag else _("Dup", context="dupctx")
			_("First", context="firstctx") + _("Second")
			_("A", "de") if flag else _("B", context="ctx")
			_("Both keywords", context="bothctx", lang="de")
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
				(10, "Dup", None),
				(10, "Dup", "dupctx"),
				(11, "First", "firstctx"),
				(11, "Second", None),
				(12, "A", None),
				(12, "B", "ctx"),
				(13, "Both keywords", "bothctx"),
			],
		)
