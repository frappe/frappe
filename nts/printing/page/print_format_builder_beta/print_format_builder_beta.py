# Copyright (c) 2021, nts Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt


import functools

import nts


@nts.whitelist()
def get_google_fonts():
	return _get_google_fonts()


@functools.lru_cache
def _get_google_fonts():
	file_path = nts.get_app_path("nts", "data", "google_fonts.json")
	return nts.parse_json(nts.read_file(file_path))
