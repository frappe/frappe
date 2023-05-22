# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.hooks import app_title
from frappe.model.document import Document


class ChangelogFeed(Document):
	pass


def get_feed():
	return [
		{
			"title": "Spid",
			"creation": "2023-04-03 16:56:51.436456",
			"app_name": app_title,
			"link": "https://frappe.io/wiki",
		},
		{
			"title": "Stable something something",
			"creation": "2023-05-03 16:56:51.436456",
			"app_name": "HRMS",
			"link": "https://frappe.io/blog",
		},
	]


def fetch_changelog_feed_items_from_source():
	"""Fetches changelog feed items from source using
	`get_changelog_feed` hook and stores in the db"""

	changelog_feed_items = []
	for fn in frappe.get_hooks("get_changelog_feed"):
		changelog_feed_items += frappe.get_attr(fn)()

	changelog_feed_items = sorted(changelog_feed_items, key=lambda x: x["creation"], reverse=True)
	for changelog_feed_item in changelog_feed_items:
		change_log_feed_item_dict = {
			"doctype": "Changelog Feed",
			"title": changelog_feed_item["title"],
			"app_name": changelog_feed_item["app_name"],
			"link": changelog_feed_item["link"],
			"creation_of_feed_item": changelog_feed_item["creation"],
		}
		if not frappe.db.exists(change_log_feed_item_dict):
			feed_doc = frappe.get_doc(change_log_feed_item_dict)
			feed_doc.insert()
	frappe.cache().delete_value("changelog_feed")


@frappe.whitelist()
def get_changelog_feed_items():
	"""Returns a list of latest 10 changelog feed items"""
	changelog_feed_items = frappe.cache().get_value("changelog_feed")
	if not changelog_feed_items or frappe.conf.developer_mode:
		fetch_changelog_feed_items_from_source()
		changelog_feed_items = frappe.get_list(
			"Changelog Feed",
			fields=["title", "app_name", "link", "creation_of_feed_item"],
			order_by="modified desc",
			limit=10,
		)
		frappe.cache().set_value("changelog_feed", changelog_feed_items, expires_in_sec=24 * 60 * 60)

	return changelog_feed_items
