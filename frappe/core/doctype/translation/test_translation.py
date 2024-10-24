# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe import _
from frappe.tests.utils import FrappeTestCase


class TestTranslation(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Translation")

	def tearDown(self):
		frappe.local.lang = "en"
		from frappe.translate import clear_cache

		clear_cache()

	def test_doctype(self):
		translation_data = get_translation_data()
		for key, val in translation_data.items():
			frappe.local.lang = key

			translation = create_translation(key, val)
			self.assertEqual(_(val[0]), val[1])

			frappe.delete_doc("Translation", translation.name)
			self.assertEqual(_(val[0]), val[0])

	def test_parent_language(self):
		data = {
			"Test Data": {
				"es": "datos de prueba",
				"es-MX": "pruebas de datos",
			},
			"Test Spanish": {
				"es": "prueba de español",
			},
		}

		for ss, lm in data.items():
			for l, st in lm.items():
				create_translation(l, (ss, st))

		frappe.local.lang = "es"

		self.assertEqual(_("Test Data"), data["Test Data"]["es"])

		self.assertEqual(_("Test Spanish"), data["Test Spanish"]["es"])

		frappe.local.lang = "es-MX"

		# different translation for es-MX
		self.assertEqual(_("Test Data"), data["Test Data"]["es-MX"])

		# from spanish (general)
		self.assertEqual(_("Test Spanish"), data["Test Spanish"]["es"])

	def test_multi_language_translations(self):
		source = "User"
		self.assertNotEqual(_(source, lang="de"), _(source, lang="es"))

	def test_html_content_data_translation(self):
		source = """
			<span style="color: rgb(51, 51, 51); font-family: &quot;Amazon Ember&quot;, Arial, sans-serif; font-size:
			small;">MacBook Air lasts up to an incredible 12 hours between charges. So from your morning coffee to
			your evening commute, you can work unplugged. When it’s time to kick back and relax,
			you can get up to 12 hours of iTunes movie playback. And with up to 30 days of standby time,
			you can go away for weeks and pick up where you left off.Whatever the task,
			fifth-generation Intel Core i5 and i7 processors with Intel HD Graphics 6000 are up to it.</span><br>
		"""

		target = """
			MacBook Air dura hasta 12 horas increíbles entre cargas. Por lo tanto,
			desde el café de la mañana hasta el viaje nocturno, puede trabajar desconectado.
			Cuando es hora de descansar y relajarse, puede obtener hasta 12 horas de reproducción de películas de iTunes.
			Y con hasta 30 días de tiempo de espera, puede irse por semanas y continuar donde lo dejó. Sea cual sea la tarea,
			los procesadores Intel Core i5 e i7 de quinta generación con Intel HD Graphics 6000 son capaces de hacerlo.
		"""

		create_translation("es", [source, target])

		source = """
			<span style="font-family: &quot;Amazon Ember&quot;, Arial, sans-serif; font-size:
			small; color: rgb(51, 51, 51);">MacBook Air lasts up to an incredible 12 hours between charges. So from your morning coffee to
			your evening commute, you can work unplugged. When it’s time to kick back and relax,
			you can get up to 12 hours of iTunes movie playback. And with up to 30 days of standby time,
			you can go away for weeks and pick up where you left off.Whatever the task,
			fifth-generation Intel Core i5 and i7 processors with Intel HD Graphics 6000 are up to it.</span><br>
		"""

		self.assertTrue(_(source), target)


def get_translation_data():
	html_source_data = """<font color="#848484" face="arial, tahoma, verdana, sans-serif">
							<span style="font-size: 11px; line-height: 16.9px;">Test Data</span></font>"""
	html_translated_data = """<font color="#848484" face="arial, tahoma, verdana, sans-serif">
							<span style="font-size: 11px; line-height: 16.9px;"> testituloksia </span></font>"""

	return {
		"hr": ["Test data", "Testdaten"],
		"ms": ["Test Data", "ujian Data"],
		"et": ["Test Data", "testandmed"],
		"es": ["Test Data", "datos de prueba"],
		"en": ["Quotation", "Tax Invoice"],
		"fi": [html_source_data, html_translated_data],
	}


def create_translation(key, val):
	translation = frappe.new_doc("Translation")
	translation.language = key
	translation.source_text = val[0]
	translation.translated_text = val[1]
	translation.save()
	return translation
