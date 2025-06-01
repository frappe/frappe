# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from urllib.parse import parse_qsl

import nts
from nts import _
from nts.twofactor import get_qr_svg_code


def get_context(context):
	context.no_cache = 1
	context.qr_code_user, context.qrcode_svg = get_user_svg_from_cache()


def get_query_key():
	"""Return query string arg."""
	query_string = nts.local.request.query_string
	query = dict(parse_qsl(query_string))
	query = {key.decode(): val.decode() for key, val in query.items()}
	if "k" not in list(query):
		nts.throw(_("Not Permitted"), nts.PermissionError)
	query = (query["k"]).strip()
	if False in [i.isalpha() or i.isdigit() for i in query]:
		nts.throw(_("Not Permitted"), nts.PermissionError)
	return query


def get_user_svg_from_cache():
	"""Get User and SVG code from cache."""
	key = get_query_key()
	totp_uri = nts.cache.get_value(f"{key}_uri")
	user = nts.cache.get_value(f"{key}_user")
	if not totp_uri or not user:
		nts.throw(_("Page has expired!"), nts.PermissionError)
	if not nts.db.exists("User", user):
		nts.throw(_("Not Permitted"), nts.PermissionError)
	user = nts.get_doc("User", user)
	svg = get_qr_svg_code(totp_uri)
	return (user, svg.decode())
