# Copyright (c) 2022, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import nts
from nts.model.document import Document, bulk_insert


class Country(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.types import DF

		code: DF.Data | None
		country_name: DF.Data
		date_format: DF.Data | None
		time_format: DF.Data | None
		time_zones: DF.Text | None
	# end: auto-generated types
	# NOTE: During installation country docs are bulk inserted.
	pass


def import_country_and_currency():
	from nts.geo.doctype.currency.currency import enable_default_currencies

	countries, currencies = get_countries_and_currencies()

	bulk_insert("Country", countries, ignore_duplicates=True)
	bulk_insert("Currency", currencies, ignore_duplicates=True)

	enable_default_currencies()


def get_countries_and_currencies():
	from nts.geo.country_info import get_all as get_geo_data

	data = get_geo_data()

	countries = []
	currencies = []

	added_currencies = set()

	for name, country in data.items():
		country = nts._dict(country)
		countries.append(
			nts.get_doc(
				doctype="Country",
				name=name,
				country_name=name,
				code=country.code,
				date_format=country.date_format or "dd-mm-yyyy",
				time_format=country.time_format or "HH:mm:ss",
				time_zones="\n".join(country.timezones or []),
			)
		)
		if country.currency and country.currency not in added_currencies:
			added_currencies.add(country.currency)

			currencies.append(
				nts.get_doc(
					doctype="Currency",
					name=country.currency,
					currency_name=country.currency,
					fraction=country.currency_fraction,
					symbol=country.currency_symbol,
					fraction_units=country.currency_fraction_units,
					smallest_currency_fraction_value=country.smallest_currency_fraction_value,
					number_format=country.number_format,
				)
			)

	return countries, currencies
