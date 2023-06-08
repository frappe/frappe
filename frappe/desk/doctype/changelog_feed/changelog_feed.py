# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

from json import loads

import requests

import frappe
from frappe.hooks import app_title
from frappe.model.document import Document


class ChangelogFeed(Document):
	pass


def get_feed(latest_date):
	source_site = "https://frappe.io"

	r = requests.get(f"{source_site}/api/method/fetch_fw_changelog")
	response = loads(r.content)

	changelog_posts = response["changelog_posts"]
	for post in changelog_posts:
		post["link"] = f"{source_site}/{post['route']}"
		post["app_name"] = app_title

	return changelog_posts


def fetch_changelog_feed_items_from_source():
	"""Fetches changelog feed items from source using
	`get_changelog_feed` hook and stores in the db"""

	latest_feed_item_date = frappe.db.get_value(
		"Changelog Feed",
		filters={},
		fieldname="creation_of_feed_item",
		order_by="creation_of_feed_item desc",
	)

	for fn in frappe.get_hooks("get_changelog_feed"):
		for changelog_feed_item in frappe.call(fn, latest_feed_item_date):
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

	# don't run in developer mode to avoid unnecessary requests
	if frappe.conf.developer_mode:
		return []

	changelog_feed_items = frappe.cache().get_value("changelog_feed")
	if not changelog_feed_items:
		latest_changelogs = frappe.get_list("Changelog Feed", limit=1, fields=["creation"])
		if (
			not latest_changelogs
			or frappe.utils.time_diff_in_seconds(frappe.utils.now_datetime(), latest_changelogs[0].creation)
			> 60
		):
			fetch_changelog_feed_items_from_source()

		changelog_feed_items = frappe.get_list(
			"Changelog Feed",
			fields=["title", "app_name", "link", "creation_of_feed_item"],
			order_by="creation_of_feed_item desc",
			limit=10,
		)
		frappe.cache().set_value("changelog_feed", changelog_feed_items, expires_in_sec=24 * 60 * 60)

	return changelog_feed_items
