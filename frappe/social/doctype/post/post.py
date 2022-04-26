# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import requests
from bs4 import BeautifulSoup

import frappe
from frappe.model.document import Document


class Post(Document):
	def on_update(self):
		if self.is_globally_pinned:
			frappe.publish_realtime("global_pin", after_commit=True)

	def after_insert(self):
		frappe.publish_realtime("new_post", self.owner, after_commit=True)


@frappe.whitelist()
def toggle_like(post_name, user=None):
	liked_by = frappe.db.get_value("Post", post_name, "liked_by")
	liked_by = liked_by.split("\n") if liked_by else []
	user = user or frappe.session.user

	if user in liked_by:
		liked_by.remove(user)
	else:
		liked_by.append(user)

	liked_by = "\n".join(liked_by)
	frappe.db.set_value("Post", post_name, "liked_by", liked_by)
	frappe.publish_realtime("update_liked_by" + post_name, liked_by, after_commit=True)


@frappe.whitelist()
def frequently_visited_links():
	return frappe.get_all(
		"Route History",
		fields=["route", "count(name) as count"],
		filters={"user": frappe.session.user},
		group_by="route",
		order_by="count desc",
		limit=5,
	)


@frappe.whitelist()
def get_link_info(url):
	cached_link_info = frappe.cache().hget("link_info", url)
	if cached_link_info:
		return cached_link_info

	try:
		page = requests.get(url)
	except (requests.exceptions.MissingSchema, requests.exceptions.ConnectionError):
		frappe.cache().hset("link_info", url, {})
		return {}

	soup = BeautifulSoup(page.text)

	meta_obj = {}
	for meta in soup.findAll("meta"):
		meta_name = meta.get("property") or meta.get("name", "").lower()
		if meta_name:
			meta_obj[meta_name] = meta.get("content")

	frappe.cache().hset("link_info", url, meta_obj)

	return meta_obj


@frappe.whitelist()
def delete_post(post_name):
	post = frappe.get_doc("Post", post_name)
	post.delete()
	frappe.publish_realtime("delete_post" + post_name, after_commit=True)


def get_unseen_post_count():
	post_count = frappe.db.count("Post")
	view_post_count = get_viewed_posts(True)

	return post_count - view_post_count


@frappe.whitelist()
def get_posts(filters=None, limit_start=0):
	filters = frappe.utils.get_safe_filters(filters)
	posts = frappe.get_list(
		"Post",
		fields=["name", "content", "owner", "creation", "liked_by", "is_pinned", "is_globally_pinned"],
		filters=filters,
		limit_start=limit_start,
		limit=20,
		order_by="is_globally_pinned desc, creation desc",
	)
	viewed_posts = get_viewed_posts()
	for post in posts:
		post["seen"] = post.name in viewed_posts
	return posts


def get_viewed_posts(only_count=False):
	view_logs = frappe.db.get_all(
		"View Log",
		filters={"reference_doctype": "Post", "viewed_by": frappe.session.user},
		fields=["reference_name"],
	)

	return len(view_logs) if only_count else [log.reference_name for log in view_logs]


@frappe.whitelist()
def set_seen(post_name):
	frappe.get_doc(
		{
			"doctype": "View Log",
			"reference_doctype": "Post",
			"reference_name": post_name,
			"viewed_by": frappe.session.user,
		}
	).insert(ignore_permissions=True)
