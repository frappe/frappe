# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt


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


def fetch_changelog_feed():
	"""Fetches changelog feed items from source using `get_changelog_feed` hook and stores in the db"""
	since = frappe.db.get_value(
		"Changelog Feed",
		filters={},
		fieldname="posting_timestamp",
		order_by="posting_timestamp desc",
	)

	for fn in frappe.get_hooks("get_changelog_feed"):
		try:
			cache_key = f"changelog_feed::{fn}"
			changelog_feed = frappe.cache.get_value(cache_key, shared=True)
			if changelog_feed is None:
				changelog_feed = frappe.call(fn, since=since)[:20] or []
				frappe.cache.set_value(
					cache_key, changelog_feed, expires_in_sec=7 * 24 * 60 * 60, shared=True
				)

			for feed_item in changelog_feed:
				feed = {
					"title": feed_item["title"],
					"app_name": feed_item["app_name"],
					"link": feed_item["link"],
					"posting_timestamp": feed_item["creation"],
				}
				if not frappe.db.exists("Changelog Feed", feed):
					frappe.new_doc("Changelog Feed").update(feed).insert()
		except Exception:
			frappe.log_error(f"Failed to fetch changelog from {fn}")
			# don't retry if it's broken for 1 week
			frappe.cache.set_value(cache_key, [], expires_in_sec=7 * 24 * 60 * 60, shared=True)


@frappe.whitelist()
@redis_cache
def get_changelog_feed_items():
	"""Returns a list of latest 10 changelog feed items"""
	return frappe.get_all(
		"Changelog Feed",
		fields=["title", "app_name", "link", "posting_timestamp"],
		# allow pubishing feed for many apps with single hook
		filters={"app_name": ("in", frappe.get_installed_apps())},
		order_by="posting_timestamp desc",
		limit=10,
	)


def get_feed(since):
	"""'What's New' feed implementation for Frappe"""
	r = requests.get(f"https://frappe.io/api/method/changelog_feed?since={since}")
	return r.json()["message"]
