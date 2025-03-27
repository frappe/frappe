from typing import Literal


def get_not_null_defaults(column_type: str) -> Literal["", 0] | None:
	"""
	Method to return a default value for a column type that is not NoneType
	:param column_type: The type of column
	:return: The value to be set
	"""
	column_type_map = {
		"Data": str,
		"Text": str,
		"Autocomplete": str,
		"Attach": str,
		"AttachImage": str,
		"Barcode": str,
		"Check": int,
		"Code": str,
		"Color": str,
		"Currency": float,
		"Date": str,
		"Datetime": str,
		"Duration": int,
		"DynamicLink": str,
		"Float": float,
		"HTMLEditor": str,
		"Int": int,
		"JSON": str,
		"Link": str,
		"LongText": str,
		"MarkdownEditor": str,
		"Password": str,
		"Percent": float,
		"Phone": str,
		"ReadOnly": str,
		"Rating": float,
		"Select": str,
		"SmallText": str,
		"TextEditor": str,
		"Time": str,
		"Table": list,
		"Table MultiSelect": list,
	}
	data_type = column_type_map.get(column_type.replace(" ", ""), str)
	# data_type = eval(f"frappe.types.DF.{column_type.replace(' ', '')}")
	if data_type is str:
		return ""
	if data_type in (int, float):
		return 0
	return None
