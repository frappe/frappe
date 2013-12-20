# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import webnotes, unittest, os
import webnotes.translate

class TestTranslations(unittest.TestCase):
	def test_doctype(self, messages=None):
		if not messages:
			messages = webnotes.translate.get_messages_from_doctype("Role")
		self.assertTrue("Role Name" in messages)

	def test_page(self, messages=None):
		if not messages:
			messages = webnotes.translate.get_messages_from_page("finder")
		self.assertTrue("Finder" in messages)
		
	def test_report(self, messages=None):
		if not messages:
			messages = webnotes.translate.get_messages_from_report("ToDo")
		self.assertTrue("Test" in messages)

	def test_include_js(self, messages=None):
		if not messages:
			messages = webnotes.translate.get_messages_from_include_files("webnotes")
		self.assertTrue("History" in messages)
		
	def test_server(self, messages=None):
		if not messages:
			messages = webnotes.translate.get_server_messages("webnotes")
		self.assertTrue("Login" in messages)
		self.assertTrue("Did not save" in messages)
		
	def test_all_app(self):
		messages = webnotes.translate.get_messages_for_app("webnotes")
		self.test_doctype(messages)
		self.test_page(messages)
		self.test_report(messages)
		self.test_include_js(messages)
		self.test_server(messages)
		
	def test_load_translations(self):
		webnotes.translate.clear_cache()
		self.assertFalse(webnotes.cache().get_value("lang:de"))
		
		langdict = webnotes.translate.get_full_dict("de")
		self.assertEquals(langdict['Row'], 'Reihe')
		
	def test_write_csv(self):
		tpath = webnotes.get_pymodule_path("webnotes", "translations", "de.csv")
		if os.path.exists(tpath):
			os.remove(tpath)
		webnotes.translate.write_translations_file("webnotes", "de")
		self.assertTrue(os.path.exists(tpath))
		self.assertEquals(dict(webnotes.translate.read_csv_file(tpath)).get("Row"), "Reihe")
		
	def test_get_dict(self):
		webnotes.local.lang = "de"
		self.assertEquals(webnotes.get_lang_dict("doctype", "Role").get("Role"), "Rolle")

if __name__=="__main__":
	webnotes.connect("site1")
	unittest.main()