# all country info
from __future__ import unicode_literals

import os, json, webnotes

def get_country_info(country=None):
	data = get_all()
	data = webnotes._dict(data.get(country, {}))
	if not 'date_format' in data:
		data.date_format = "dd-mm-yyyy"
			
	return data

@webnotes.whitelist()
def get_all():
	with open(os.path.join(os.path.dirname(__file__), "country_info.json"), "r") as local_info:
		all_data = json.loads(local_info.read())
	return all_data

	
