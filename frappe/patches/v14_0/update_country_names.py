import frappe


def execute():
	country_info_map = {
		"Taiwan": "Taiwan, Province of China",
		"Tanzania": "Tanzania, United Republic of",
		"Vietnam": "Viet Nam",
		"Congo, The Democratic Republic of the": "Congo, Democratic Republic of the",
	}

	for old, new in country_info_map.items():
		frappe.rename_doc("Country", old, new, force=True)
