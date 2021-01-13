from __future__ import unicode_literals
from frappe import _

def get_data():
	return {
		'fieldname': 'user_type',
		'transactions': [
			{
				'label': _('Reference'),
				'items': ['User']
			}
		]
	}