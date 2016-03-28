# Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from __future__ import unicode_literals

import frappe, re, frappe.utils
from frappe.desk.notifications import get_notifications
from frappe import _

class BotParser(object):
	'''Base class for bot parser'''
	def __init__(self, reply, query):
		self.query = query
		self.reply = reply
		self.tables = reply.tables
		self.doctype_names = reply.doctype_names

	def has(self, *words):
		'''return True if any of the words is present int the query'''
		for word in words:
			if re.search(r'\b{0}\b'.format(word), self.query):
				return True

	def startswith(self, *words):
		'''return True if the query starts with any of the given words'''
		for w in words:
			if self.query.startswith(w):
				return True

	def strip_words(self, query, *words):
		'''Remove the given words from the query'''
		for word in words:
			query = re.sub(r'\b{0}\b'.format(word), '', query)

		return query.strip()

class ShowNotificationBot(BotParser):
	'''Show open notifications'''
	def get_reply(self):
		if self.has("whatsup", "what's up", "wassup", "whats up"):
			n = get_notifications()
			open_items = sorted(n.get('open_count_doctype').items())

			if open_items:
				return ("Following items need your attention:\n\n"
					+ "\n\n".join(["{0} [{1}](#List/{1})".format(d[1], d[0])
						for d in open_items if d[1] > 0]))
			else:
				return 'Take it easy, nothing urgent needs your attention'

class GetOpenListBot(BotParser):
	'''Get list of open items'''
	def get_reply(self):
		if self.startswith('open', 'show open', 'list open', 'get open'):
			if self.tables:
				doctype = self.doctype_names[self.tables[0]]
				from frappe.desk.notifications import get_notification_config
				filters = get_notification_config().get('for_doctype').get(doctype, None)
				if filters:
					if isinstance(filters, dict):
						data = frappe.get_list(doctype, filters=filters)
					else:
						data = [{'name':d[0], 'title':d[1]} for d in frappe.get_attr(filters)(as_list=True)]

					return ", ".join('[{title}](#Form/{doctype}/{name})'.format(doctype=doctype,
						name=d.get('name'), title=d.get('title') or d.get('name')) for d in data)
				else:
					return _("Can't identify open {0}. Try something else.").format(doctype)

class SQLQueryBot(BotParser):
	'''Try and build an SQL query from the question'''
	def get_reply(self):
		self.out = ''
		self.function = ''
		self.fields = []
		self.conditions = []
		self.order_by = ''
		self.limit = ''

		if self.tables:
			self.identify_function()

		if self.out:
			return self.out

		if self.fields:
			sql = 'select {fields} from {tables} {where} {conditions} {order_by} {limit}'.format(
				fields = ', '.join(self.fields),
				tables = ', '.join(['`tab{0}`'.format(self.doctype_names[t]) for t in self.tables]),
				where = 'where' if self.conditions else '',
				conditions = (' '.join([c[0] + ' ' + c[1] for c in self.conditions])
					if self.conditions else ''),
				order_by = 'order by {0}'.format(self.order_by) if self.order_by else '',
				limit = 'limit {0}'.format(self.limit) if self.limit else ''
			)
			reply = self.format_result(frappe.db.sql(sql))
			return reply or _("Cound not find what you were searching for")

	def format_result(self, data):
		out = []
		for d in data:
			if self.fields[0]=='name':
				row = '[{name}](#Form/{table}/{name})'.format(name = d[0],
					table=self.doctype_names[self.tables[0]])
			else:
				row = d[0]

			out.append(row)

		return ', '.join(out)

	def identify_function(self):
		self.function = None

		if 'how many' in self.query:
			self.fields.append('count(*)')

		elif 'oldest' in self.query:
			self.fields.append('name')
			self.order_by = 'creation asc'
			self.limit = '1'

		elif self.has('newest', 'latest'):
			self.fields.append('name')
			self.order_by = 'creation desc'
			self.limit = '1'

		elif self.has('made by whom', 'who created', 'who made'):
			self.fields.append('owner')

		elif self.has('changed by whom', 'who changed', 'who updated'):
			self.fields.append('modified_by')

		elif self.has('list', 'show'):
			self.fields.append('name')

		elif self.startswith('find'):
			table = None
			query = self.query

			query = self.strip_words(query, 'find')

			if self.has('from'):
				text, table = query.split('from')

			if self.has('in'):
				text, table = query.split('in')

			if table:
				text = text.strip()
				self.tables = self.reply.identify_tables(table)

				if self.tables:
					if 'name' not in self.fields:
						self.fields.append('name')

					self.conditions.append(('', 'name like "%{0}%"'.format(text)))
					title_field = frappe.get_meta(self.tables[0]).title_field
					if title_field and title_field!='name':
						self.conditions.append(('or', '{0} like "%{1}%"'.format(title_field, text)))

				else:
					self.out = _("Could not identify {0}").format(table)
			else:
				self.out = _("You can find things by asking 'find orange in customers'").format(table)

class BotReply(object):
	'''Build a reply for the bot by calling all parsers'''
	def __init__(self):
		self.tables = []

	def get_reply(self, query):
		self.query = query.lower()
		self.setup()
		self.pre_process()

		# basic replies
		if self.query.split()[0] in ("hello", "hi"):
			return _("Hello {0}").format(frappe.utils.get_fullname())

		if self.query == "help":
			return help_text.format(frappe.utils.get_fullname())

		# build using parsers
		replies = []
		for parser in frappe.get_hooks('bot_parsers'):
			reply = frappe.get_attr(parser)(self, query).get_reply()
			if reply:
				replies.append(reply)

		if replies:
			return '\n\n'.join(replies)

		if not reply:
			return _("Don't know, ask 'help'")

	def setup(self):
		self.setup_tables()
		self.identify_tables()

	def pre_process(self):
		if self.query.endswith("?"):
			self.query = self.query[:-1]

		if self.query in ("todo", "to do"):
			self.query = "open todo"

	def setup_tables(self):
		tables = frappe.get_all("DocType", {"is_table": 0})
		self.all_tables = [d.name.lower() for d in tables]
		self.doctype_names = {d.name.lower():d.name for d in tables}

	def identify_tables(self, query=None):
		if not query:
			query = self.query
		self.tables = []
		for t in self.all_tables:
			if t in query or t[:-1] in query:
				self.tables.append(t)

		return self.tables



help_text = """Hello {0}, I am a K.I.S.S Bot, not AI, so be kind. I can try answering a few questions like,

- "todo": list my todos
- "show customers": list customers
- "locate shirt": find where to find item "shirt"
- "open issues": find open issues, try "open sales orders"
- "how many users": count number of users
- "find asian in sales orders": find sales orders where name or title has "asian"

have fun!
"""