# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import unittest
import frappe

from frappe.utils import global_search
import frappe.utils

class TestGlobalSearch(unittest.TestCase):
	def setUp(self):
		global_search.setup_table()
		self.assertTrue('__global_search' in frappe.db.get_tables())

		doctype = "Event"
		# from frappe.custom.doctype.property_setter.property_setter import make_property_setter
		# make_property_setter(doctype, "subject", "in_global_search", 1, "Int")

		global_search.reset()

		self.insert_test_events()

		event_doctype = frappe.get_doc('DocType', doctype)
		event_doctype.validate()
		event_doctype.sync_global_search()


	def insert_test_events(self):
		phrases1 = ['"The Sixth Extinction II: Amor Fati" is the second episode of the seventh season of the American science fiction.','After Mulder awakens from his coma, he realizes his duty to prevent alien colonization. ',"Carter explored themes of extraterrestrial involvement in ancient mass extinctions in this episode, the third in a trilogy."]
		phrases2 = ['Hydrus is a small constellation in the deep southern sky. ','It was first depicted on a celestial atlas by Johann Bayer in his 1603 Uranometria. ','The French explorer and astronomer Nicolas Louis de Lacaille charted the brighter stars and gave their Bayer designations in 1756. ','Its name means "male water snake", as opposed to Hydra, a much larger constellation that represents a female water snake. ','It remains below the horizon for most Northern Hemisphere observers.',
		'The brightest star is the 2.8-magnitude Beta Hydri, also the closest reasonably bright star to the south celestial pole. ','Pulsating between magnitude 3.26 and 3.33, Gamma Hydri is a variable red giant some 60 times the diameter of our Sun. ','Lying near it is VW Hydri, one of the brightest dwarf novae in the heavens. ','Four star systems have been found to have exoplanets to date, most notably HD 10180, which could bear up to nine planetary companions.']
		phrases3 = ['Keyzer and de Houtman assigned 15 stars to the constellation in their Malay and Madagascan vocabulary, with a star that ','Gamma the chest and a number of stars that were later allocated to Tucana, Reticulum, Mensa and Horologium marking the body and tail. ','Lacaille charted and designated 20 stars with the Bayer designations Alpha through to Tau in 1756. ','Of these, he used the designations Eta, Pi and Tau twice each, for three sets of two stars close together, and omitted Omicron and Xi. ','He assigned Rho to a star that subsequent astronomers were unable to find.']
		phrases = phrases1 + phrases2 + phrases3;

		for text in phrases:
			frappe.get_doc(dict(
				doctype='Event',
				subject=text,
				starts_on=frappe.utils.now_datetime())).insert()

		frappe.db.commit()

	def test_search(self):
		search_table = frappe.db.sql('''select * from __global_search''', as_dict=True)
		print search_table
		phrases = ['"The Sixth Extinction II: Amor Fati" is the second episode of the seventh season of the American science fiction.',
			'After Mulder awakens from his coma, he realizes his duty to prevent alien colonization. ',
			"Carter explored themes of extraterrestrial involvement in ancient mass extinctions in this episode, the third in a trilogy."
		]

		events = []
		for text in phrases:
			events.append(frappe.get_doc('Event', dict(subject=text)))

		results = global_search.search('awakens')
		self.assertDictEqual(dict(doctype='Event', name=events[1].name, content=events[1].subject), results[0])

		results = global_search.search('extraterrestrial')
		self.assertDictEqual(dict(doctype='Event', name=events[2].name, content=events[2].subject), results[0])

	def test_insert(self):
		test_subject = 'testing global search'

		existing = frappe.db.get_value('Event', dict(subject=test_subject))
		if existing:
			frappe.delete_doc('Event', existing)

		global_search.reset()

		phrases = ['"The Sixth Extinction II: Amor Fati" is the second episode of the seventh season of the American science fiction television series The X-Files.',
			'After Mulder awakens from his coma, he realizes his duty to prevent alien colonization. ',
			"Carter explored themes of extraterrestrial involvement in ancient mass extinctions in this episode, the third in a trilogy focused on Mulder's severe reaction to an alien artifact."
		]

		events = []
		for text in phrases:
			events.append(frappe.get_doc(dict(
				doctype='Event',
				subject=text,
				starts_on=frappe.utils.now_datetime())).insert())

		frappe.db.commit()

		results = global_search.search('awakens')
		self.assertDictEqual(dict(doctype='Event', name=events[1].name), results[0])

		results = global_search.search('extraterrestrial')
		self.assertDictEqual(dict(doctype='Event', name=events[2].name), results[0])

	# def tearDown(self):
	# 	print "The property setter table before"
	# 	print frappe.db.sql('select * from `tabProperty Setter`')
	# 	frappe.db.sql('delete from `tabProperty Setter`')

	# 	frappe.clear_cache(doctype='Event')