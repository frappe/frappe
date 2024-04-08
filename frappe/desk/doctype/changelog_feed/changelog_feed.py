# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt


from contextlib import suppress

import requests

import frappe
from frappe.model.document import Document
from frappe.utils.caching import redis_cache


class ChangelogFeed(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		app_name: DF.Data | None
		link: DF.LongText
		posting_timestamp: DF.Datetime
		title: DF.Data
	# end: auto-generated types

	pass


def get_feed(since):
	r = requests.get(f"https://frappe.io/api/method/fetch_changelog?since={since}").json()
	changelog_posts = r["message"]
	return changelog_posts


def fetch_changelog_feed_items_from_source():
	"""Fetches changelog feed items from source using `get_changelog_feed` hook and stores in the db"""
	since = frappe.db.get_value(
		"Changelog Feed",
		filters={},
		fieldname="posting_timestamp",
		order_by="posting_timestamp desc",
	)

	for fn in frappe.get_hooks("get_changelog_feed"):
		with suppress(Exception):
			for changelog_feed_item in frappe.call(fn, since=since):
				change_log_feed_item_dict = {
					"doctype": "Changelog Feed",
					"title": changelog_feed_item["title"],
					"app_name": changelog_feed_item["app_name"],
					"link": changelog_feed_item["link"],
					"posting_timestamp": changelog_feed_item["creation"],
				}
				if not frappe.db.exists(change_log_feed_item_dict):
					feed_doc = frappe.new_doc("Changelog Feed")
					feed_doc.update(change_log_feed_item_dict)
					feed_doc.insert()


@frappe.whitelist()
@redis_cache
def get_changelog_feed_items():
	"""Returns a list of latest 10 changelog feed items"""
	return frappe.get_all(
		"Changelog Feed",
		fields=["title", "app_name", "link", "posting_timestamp"],
		order_by="posting_timestamp desc",
		limit=10,
	)
