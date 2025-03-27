import json

import pycountry
import requests

import frappe


class Here:
	def __init__(self, api_key: str, lang: str | None = None):
		self.lang = lang
		self.api_key = api_key
		self.base_url = "https://autocomplete.search.hereapi.com/v1"

	def autocomplete(self, query: str):
		params = {
			"q": query,
			"apiKey": self.api_key,
			"limit": 5,
			"lang": self.lang,
		}
		response = requests.get(
			f"{self.base_url}/autocomplete",
			params=params,
		)
		response.raise_for_status()

		results = response.json()["items"]
		for result in results:
			address = result["address"]
			py_country = pycountry.countries.get(alpha_3=address.get("countryCode"))
			frappe_country = frappe.db.get_value("Country", {"code": py_country.alpha_2.lower()})
			yield {
				"label": address["label"],
				"value": json.dumps(
					{
						"address_line1": f'{address.get("street", "")} {address.get("houseNumber", "")}'.strip(),
						"city": address.get("city", ""),
						"state": address.get("state", ""),
						"pincode": address.get("postalCode", ""),
						"country": frappe_country or "",
					}
				),
			}
