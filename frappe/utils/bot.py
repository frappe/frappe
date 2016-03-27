# Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from __future__ import unicode_literals

import frappe, re, frappe.utils
from frappe.desk.notifications import get_notifications
from frappe import _

class BotReply(object):
	def __init__(self):
		self.tables = []
		self.function = ''
		self.fields = []
		self.conditions = []
		self.order_by = ''
		self.limit = ''
		self.setup()

	def get_reply(self, query):
		self.query = query.lower()

		if self.query.endswith("?"):
			self.query = self.query[:-1]

		if self.has("todo", "to do"):
			self.query = "open todo"

		if self.has("hello", "hi"):
			return _("Hello {0}").format(frappe.utils.get_fullname())

		if self.has("help"):
			return help_text.format(frappe.utils.get_fullname())

		elif self.has("whatsup", "what's up", "wassup", "whats up"):
			n = get_notifications()
			return ", ".join(["{0} [{1}](#List/{1})".format(d[1], d[0])
				for d in sorted(n.get('open_count_doctype').items()) if d[1] > 0]) + " need your attention"

		elif self.startswith('where is', 'find item', 'locate'):
			item = '%{0}%'.format(self.strip_words(self.query, 'where is', 'find item', 'locate'))
			items = frappe.db.sql('''select name from `tabItem` where item_code like %(txt)s
				or item_name like %(txt)s or description like %(txt)s''', dict(txt=item))

			if items:
				out = []
				warehouses = frappe.get_all("Warehouse")
				for item in items:
					found = False
					for warehouse in warehouses:
						qty = frappe.db.get_value("Bin", {'item_code': item[0], 'warehouse': warehouse.name}, 'actual_qty')
						if qty:
							out.append(_('{0} units of [{1}](#Form/Item/{1}) found in [{2}](#Form/Warehouse/{2})').format(qty,
								item[0], warehouse.name))
							found = True

					if not found:
						out.append(_('[{0}](#Form/Item/{0}) is out of stock').format(item[0]))

				return "\n\n".join(out)

			else:
				return _("Did not find any item called {0}".format(item))

		elif self.startswith('open', 'show open', 'list open', 'get open'):
			self.identify_tables()

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

		elif self.parse_for_sql():
			out = []
			for d in self.data:
				if self.fields[0]=='name':
					row = '[{name}](#Form/{table}/{name})'.format(name = d[0],
						table=self.doctype_names[self.tables[0]])
				else:
					row = d[0]

				out.append(row)

			return ', '.join(out)
		else:
			return _("Don't know, ask 'help'")

	def parse_for_sql(self):
		self.identify_tables()
		if self.tables:
			self.identify_function()


		if self.fields:
			sql = 'select {fields} from {tables} {where} {conditions} {order_by} {limit}'.format(
				fields = ', '.join(self.fields),
				tables = ', '.join(['`tab{0}`'.format(t) for t in self.tables]),
				where = 'where' if self.conditions else '',
				conditions = (' '.join([c[0] + ' ' + c[1] for c in self.conditions])
					if self.conditions else ''),
				order_by = 'order by {0}'.format(self.order_by) if self.order_by else '',
				limit = 'limit {0}'.format(self.limit) if self.limit else ''
			)
			self.data = frappe.db.sql(sql)

			return True
		else:
			return None

	def setup(self):
		self.setup_tables()

	def setup_tables(self):
		tables = frappe.get_all("DocType", {"is_table": 0})
		self.all_tables = [d.name.lower() for d in tables]
		self.doctype_names = {d.name.lower():d.name for d in tables}

	def identify_tables(self):
		self.tables = []
		for t in self.all_tables:
			if t in self.query or t[:-1] in self.query:
				self.tables.append(t)

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

		elif self.has('find'):
			query = self.query

			query = self.strip_words(query, 'find', 'in', 'from', 'for')

			# strip table name
			query = self.strip_words(query, *self.tables)
			# plurals
			query = self.strip_words(query, *[t + 's' for t in self.tables])

			text = query.strip()
			self.fields.append('name')

			self.conditions.append(('', 'name like "%{0}%"'.format(text)))
			title_field = frappe.get_meta(self.tables[0]).title_field
			if title_field:
				self.conditions.append(('or', '{0} like "%{1}%"'.format(title_field, text)))


	def strip_words(self, query, *words):
		for word in words:
			query = re.sub(r'\b{0}\b'.format(word), '', query)

		return query.strip()

	def has(self, *words):
		for w in words:
			if w in self.query:
				return True

	def startswith(self, *words):
		for w in words:
			if self.query.startswith(w):
				return True

help_text = """Hello {0}, I am a K.I.S.S Bot, not AI, so be kind. I can try answering a few questions like,

- "todo": list my todos
- "show customers": list customers
- "locate shirt": find where to find item "shirt"
- "open issues": find open issues, try "open sales orders"
- "how many users": count number of users
- "find asian in sales orders": find sales orders where name or title has "asian"

have fun!
"""