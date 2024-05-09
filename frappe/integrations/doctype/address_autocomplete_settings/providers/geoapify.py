import json

import requests


class GeoapifyProvider:
	def __init__(self, api_key: str, lang: str | None = None):
		self.api_key = api_key
		self.lang = lang
		self.base_url = "https://api.geoapify.com"

	def autocomplete(self, query: str) -> list[dict]:
		params = {
			"text": query,
			"apiKey": self.api_key,
			"limit": 20,
			"format": "json",
			"lang": self.lang,
		}
		response = requests.get(f"{self.base_url}/v1/geocode/autocomplete", params=params)
		response.raise_for_status()

		results = response.json()["results"]
		# TODO: need to return the full address data here, as value or extra data
		return [
			{
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
			for result in results
		]
