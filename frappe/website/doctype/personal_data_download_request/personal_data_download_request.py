# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_email_address, get_user_by_email, get_user_display_id
from frappe.utils.verified_command import get_signed_params
from frappe.website.doctype.personal_data_deletion_request.personal_data_deletion_request import (
	get_user_values,
)


class PersonalDataDownloadRequest(Document):
	_DOCTYPE_NAME = "Personal Data Download Request"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amended_from: DF.Link | None
		user: DF.Link
		user_name: DF.Data | None
	# end: auto-generated types

	def as_dict(self, *args, **kwargs):
		d = super().as_dict(*args, **kwargs)
		d.pop("user_name", None)
		return d

	def insert(self, *args, **kwargs):
		requested = self.user
		user = requested and (get_user_by_email(requested) or frappe.db.get_value("User", requested))
		if not user:
			self.name = frappe.generate_hash(length=10)
			self.set_user_and_timestamp()
			self.user_name = ""
			self.set("__islocal", False)
			self.set("__unsaved", False)
			return self

		self.user = user
		super().insert(*args, **kwargs)
		# echo the request back so the response does not reveal the user's ID
		self.user = requested
		return self

	def after_insert(self):
		personal_data = get_user_data(self.user)

		frappe.enqueue_doc(
			self.doctype,
			self.name,
			"generate_file_and_send_mail",
			queue="short",
			personal_data=personal_data,
			now=frappe.in_test,
		)

	def generate_file_and_send_mail(self, personal_data):
		"""generate the file link for download"""
		user_name = self.user_name.replace(" ", "-")
		f = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "Personal-Data-" + user_name + "-" + self.name + ".json",
				"attached_to_doctype": "Personal Data Download Request",
				"attached_to_name": self.name,
				"content": str(personal_data),
				"is_private": 1,
			}
		)
		f.flags.skip_file_size_check = True
		f.save(ignore_permissions=True)

		# Bind ownership
		frappe.db.set_value("File", f.name, "owner", self.user)
		self.db_set("owner", self.user)

		file_link = (
			frappe.utils.get_url("/api/method/frappe.utils.file_manager.download_file")
			+ "?"
			+ get_signed_params({"file_url": f.file_url})
		)
		host_name = frappe.local.site
		frappe.sendmail(
			recipients=get_email_address(self.user),
			subject=_("Download Your Data"),
			template="download_data",
			args={
				"user": get_user_display_id(self.user),
				"user_name": self.user_name,
				"link": file_link,
				"host_name": host_name,
			},
			header=[_("Download Your Data"), "green"],
		)


def get_user_data(user):
	"""Return user data not linked to `User` doctype."""
	hooks = frappe.get_hooks("user_data_fields")
	values = get_user_values(user, get_email_address(user))
	data = {}
	for hook in hooks:
		doctype = hook.get("doctype")
		filter_by = hook.get("filter_by", "owner")
		d = data.get(doctype, [])
		d += frappe.get_all(doctype, {filter_by: ("in", values)}, ["*"])
		if d:
			data.update({doctype: d})
	return json.dumps(data, indent=2, default=str)
