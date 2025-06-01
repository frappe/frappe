# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import nts
from nts.utils import strip_html_tags
from nts.utils.html_utils import clean_html

no_cache = 1


def get_context(context):
	message_context = nts._dict()
	if hasattr(nts.local, "message"):
		message_context["header"] = nts.local.message_title
		message_context["title"] = strip_html_tags(nts.local.message_title)
		message_context["message"] = nts.local.message
		if hasattr(nts.local, "message_success"):
			message_context["success"] = nts.local.message_success

	elif nts.local.form_dict.id:
		message_id = nts.local.form_dict.id
		key = f"message_id:{message_id}"
		message = nts.cache.get_value(key, expires=True)
		if message:
			message_context.update(message.get("context", {}))
			if message.get("http_status_code"):
				nts.local.response["http_status_code"] = message["http_status_code"]

	if not message_context.title:
		message_context.title = clean_html(nts.form_dict.title)

	if not message_context.message:
		message_context.message = clean_html(nts.form_dict.message)

	return message_context
