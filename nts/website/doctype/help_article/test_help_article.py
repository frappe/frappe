# Copyright (c) 2015, nts Technologies and Contributors
# License: MIT. See LICENSE
import nts
from nts.tests.utils import ntsTestCase

# test_records = nts.get_test_records('Help Article')


class TestHelpArticle(ntsTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		cls.help_category = nts.get_doc(
			{
				"doctype": "Help Category",
				"category_name": "_Test Help Category",
			}
		).insert()

		cls.help_article = nts.get_doc(
			{
				"doctype": "Help Article",
				"title": "_Test Article",
				"category": cls.help_category.name,
				"content": "_Test Article",
			}
		).insert()

	def test_article_is_helpful(self):
		from nts.website.doctype.help_article.help_article import add_feedback

		self.help_article.load_from_db()
		self.assertEqual(self.help_article.helpful, 0)
		self.assertEqual(self.help_article.not_helpful, 0)

		add_feedback(self.help_article.name, "Yes")
		add_feedback(self.help_article.name, "No")

		self.help_article.load_from_db()
		self.assertEqual(self.help_article.helpful, 1)
		self.assertEqual(self.help_article.not_helpful, 1)

	def test_category_disable(self):
		self.help_article.load_from_db()
		self.help_article.published = 1
		self.help_article.save()

		self.help_category.load_from_db()
		self.help_category.published = 0
		self.help_category.save()

		self.help_article.load_from_db()
		self.assertEqual(self.help_article.published, 0)

	@classmethod
	def tearDownClass(cls) -> None:
		nts.delete_doc(cls.help_article.doctype, cls.help_article.name)
		nts.delete_doc(cls.help_category.doctype, cls.help_category.name)
