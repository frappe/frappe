# Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from __future__ import unicode_literals

import frappe, re, frappe.utils
from frappe.desk.notifications import get_notifications
from frappe import _

@frappe.whitelist()
def get_bot_reply(question):
	return BotReply().get_reply(question)

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

	def format_list(self, data):
		'''Format list as markdown'''
		return _('I found these: ') + ', '.join([' [{title}](/app/Form/{doctype}/{name})'.format(
			title = d.title or d.name,
			doctype=self.get_doctype(),
			name=d.name) for d in data])

	def get_doctype(self):
		'''returns the doctype name from self.tables'''
		return self.doctype_names[self.tables[0]]

class ShowNotificationBot(BotParser):
	'''Show open notifications'''
	def get_reply(self):
		if self.has("whatsup", "what's up", "wassup", "whats up", 'notifications', 'open tasks'):
			n = get_notifications()
			open_items = sorted(n.get('open_count_doctype').items())

			if open_items:
				return ("Following items need your attention:\n\n"
					+ "\n\n".join(["{0} [{1}](/app/List/{1})".format(d[1], d[0])
						for d in open_items if d[1] > 0]))
			else:
				return 'Take it easy, nothing urgent needs your attention'

class GetOpenListBot(BotParser):
	'''Get list of open items'''
	def get_reply(self):
		if self.startswith('open', 'show open', 'list open', 'get open'):
			if self.tables:
				doctype = self.get_doctype()
				from frappe.desk.notifications import get_notification_config
				filters = get_notification_config().get('for_doctype').get(doctype, None)
				if filters:
					if isinstance(filters, dict):
						data = frappe.get_list(doctype, filters=filters)
					else:
						data = [{'name':d[0], 'title':d[1]} for d in frappe.get_attr(filters)(as_list=True)]

					return ", ".join('[{title}](/app/Form/{doctype}/{name})'.format(doctype=doctype,
						name=d.get('name'), title=d.get('title') or d.get('name')) for d in data)
				else:
					return _("Can't identify open {0}. Try something else.").format(doctype)

class ListBot(BotParser):
	def get_reply(self):
		if self.query.endswith(' ' + _('list')) and self.startswith(_('list')):
			self.query = _('list') + ' ' + self.query.replace(' ' + _('list'), '')
		if self.startswith(_('list'), _('show')):
			like = None
			if ' ' + _('like') + ' ' in self.query:
				self.query, like = self.query.split(' ' + _('like') + ' ')

			self.tables = self.reply.identify_tables(self.query.split(None, 1)[1])
			if self.tables:
				doctype = self.get_doctype()
				meta = frappe.get_meta(doctype)
				fields = ['name']
				if meta.title_field:
					fields.append('`{0}` as title'.format(meta.title_field))

				filters = {}
				if like:
					filters={
						meta.title_field or 'name': ('like', '%' + like + '%')
					}
				return self.format_list(frappe.get_list(self.get_doctype(), fields=fields, filters=filters))

class CountBot(BotParser):
	def get_reply(self):
		if self.startswith('how many'):
			self.tables = self.reply.identify_tables(self.query.split(None, 1)[1])
			if self.tables:
				return str(frappe.db.sql('select count(*) from `tab{0}`'.format(self.get_doctype()))[0][0])

class FindBot(BotParser):
	def get_reply(self):
		if self.startswith('find', 'search'):
			query = self.query.split(None, 1)[1]

			if self.has('from'):
				text, table = query.split('from')

			if self.has('in'):
				text, table = query.split('in')

			if table:
				text = text.strip()
				self.tables = self.reply.identify_tables(table.strip())


				if self.tables:
					filters = {'name': ('like',  '%{0}%'.format(text))}
					or_filters = None

					title_field = frappe.get_meta(self.get_doctype()).title_field
					if title_field and title_field!='name':
						or_filters = {'title': ('like',  '%{0}%'.format(text))}

					data = frappe.get_list(self.get_doctype(),
						filters=filters, or_filters=or_filters)
					if data:
						return self.format_list(data)
					else:
						return _("Could not find {0} in {1}").format(text, self.get_doctype())

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
			reply = None
			try:
				reply = frappe.get_attr(parser)(self, query).get_reply()
			except frappe.PermissionError:
				reply = _("Oops, you are not allowed to know that")

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
		tables = frappe.get_all("DocType", {"istable": 0})
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
- "show customers like giant": list customer containing giant
- "locate shirt": find where to find item "shirt"
- "open issues": find open issues, try "open sales orders"
- "how many users": count number of users
- "find asian in sales orders": find sales orders where name or title has "asian"

have fun!
"""
