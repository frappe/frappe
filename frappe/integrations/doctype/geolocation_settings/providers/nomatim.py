import json

import requests

import frappe


class Nomatim:
	def __init__(self, base_url: str, referer: str, lang: str | None = None):
		self.lang = lang
		self.referer = referer
		self.base_url = base_url

	def autocomplete(self, query: str):
		params = {
			"q": query,
			"format": "json",
			"limit": 5,
			"addressdetails": 1,
			"accept-language": self.lang,
			"layer": "address",
		}
		response = requests.get(
			f"{self.base_url}/search",
			params=params,
			headers={"Referer": self.referer},
		)
		response.raise_for_status()

		results = response.json()
		for result in results:
			if "address" not in result:
				continue

			address = result["address"]
			yield {
				"label": result["display_name"],
				"value": json.dumps(
					{
						"address_line1": f'{address.get("road")} {address.get("house_number", "")}'.strip(),
						"city": address.get("city") or address.get("town") or address.get("village"),
						"state": address.get("state"),
						"pincode": address.get("postcode"),
						"country": frappe.db.get_value("Country", {"code": address.get("country_code")}),
					}
				),
			}
