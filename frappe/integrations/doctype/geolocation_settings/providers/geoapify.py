import json

import requests


class Geoapify:
	def __init__(self, api_key: str, lang: str | None = None):
		self.api_key = api_key
		self.lang = lang
		self.base_url = "https://api.geoapify.com"

	def autocomplete(self, query: str):
		params = {
			"text": query,
			"apiKey": self.api_key,
			"limit": 5,
			"format": "json",
			"lang": self.lang,
		}
		response = requests.get(f"{self.base_url}/v1/geocode/autocomplete", params=params)
		response.raise_for_status()

		results = response.json()["results"]
		for result in results:
			yield {
				"label": result["formatted"],
				"value": json.dumps(
					{
						"address_line1": result.get("address_line1"),
						"city": result.get("city"),
						"state": result.get("state"),
						"pincode": result.get("postcode"),
						"country": result.get("country"),
					}
				),
			}
