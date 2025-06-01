import nts
from nts.core.doctype.doctype.test_doctype import new_doctype
from nts.tests.utils import ntsTestCase
from nts.www.printview import get_html_and_style


class PrintViewTest(ntsTestCase):
	def test_print_view_without_errors(self):
		user = nts.get_last_doc("User")

		messages_before = nts.get_message_log()
		ret = get_html_and_style(doc=user.as_json(), print_format="Standard", no_letterhead=1)
		messages_after = nts.get_message_log()

		if len(messages_after) > len(messages_before):
			new_messages = messages_after[len(messages_before) :]
			self.fail("Print view showing error/warnings: \n" + "\n".join(str(msg) for msg in new_messages))

		# html should exist
		self.assertTrue(bool(ret["html"]))

	def test_print_error(self):
		"""Print failures shouldn't generate PDF with failure message but instead escalate the error"""
		doctype = new_doctype(is_submittable=1).insert()

		doc = nts.new_doc(doctype.name)
		doc.insert()
		doc.submit()
		doc.cancel()

		# cancelled doc can't be printed by default
		self.assertRaises(nts.PermissionError, nts.attach_print, doc.doctype, doc.name)
