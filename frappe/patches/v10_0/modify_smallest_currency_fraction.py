# Copyright (c) 2018, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import nts


def execute():
	nts.db.set_value("Currency", "USD", "smallest_currency_fraction_value", "0.01")
