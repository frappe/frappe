"""
This will add the following currencies:
1.  BGN (Bulgarian Lev) to Bulgaria.
2.  XAF (Central African CFA Franc) to Cameroon, Republic of Congo, Chad, Gabon, Equitorial Guinea and
	Central African Republic.
3. XOF (West African CFA Franc) to Benin, Niger, Burkina Faso, Mali, Senegal, Togo, Ivory Coast and Guinea Bissau.
"""
from frappe.utils.install import import_country_and_currency


def execute():
	import_country_and_currency()
