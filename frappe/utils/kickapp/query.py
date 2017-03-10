from __future__ import unicode_literals
import frappe
from frappe.utils.kickapp.helper import Helper


class Query(object):
	def __init__(self, bot_name):
		self.bot_name = bot_name.lower()
		self.actions = Helper().get_doctype_actions_from_bot_name(bot_name)
	
	def get_action_from_text(self, text):
		count_array = self.get_count_array(text)
		print count_array
		index = count_array.index(max(count_array))
		if index > -1:
			return self.actions[index]
		return 'error'
	
	def get_count_array(self, text):
		count_array = []
		for x in self.actions:
			count_array.append(sum(i == j for i, j in zip(text.lower(), x)))
		return count_array
	# def create_keywords(self, doctype):
	# 	return ['create', 
	# 			'{0} {1}'.format('create new', doctype), 
	# 			'{0} {1}'.format('create a', doctype),
	# 			'{0} {1}'.format('create my', doctype),
	# 			'{0} {1}'.format('create', doctype),
	# 			'{0} {1}'.format('hey create new', doctype),
	# 			'{0} {1}'.format('hey create', doctype),
	# 			'{0} {1}'.format('make new', doctype),
	# 			'{0} {1}'.format('make a', doctype),
	# 			'{0} {1}'.format('make', doctype)]

	# def update_keywords(self, doctype):
	# 	return ['update', 
	# 			'{0} {1}'.format('update', doctype),
	# 			'{0} {1}'.format('update a', doctype),
	# 			'{0} {1}'.format('update my', doctype)]

	# def delete_keywords(self, doctype):
	# 	return ['delete', '{0} {1}'.format('delete', doctype),
	# 			'{0} {1}'.format('delete a', doctype),
	# 			'{0} {1}'.format('delete my', doctype)]

	# def get_keywords(self, doctype):
	# 	return ['get', 
	# 			'list', '{0} {1}'.format('list', doctype), 
	# 			'{0} {1}'.format('get', doctype),
	# 			'{0} {1}'.format('get all', doctype),
	# 			'{0} {1}'.format('get my', doctype),
	# 			'{0} {1} {2}'.format('get', doctype, 's'),
	# 			'{0} {1} {2}'.format('get all', doctype, 's'),
	# 			'{0} {1} {2}'.format('get my', doctype, 's')]