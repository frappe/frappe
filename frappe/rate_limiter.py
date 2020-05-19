# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

from datetime import datetime
import frappe
from frappe import _
from frappe.utils import cint
from werkzeug.wrappers import Response


def apply():
	rate_limit = frappe.conf.rate_limit
	if rate_limit:
		frappe.local.rate_limiter = RateLimiter(rate_limit["limit"], rate_limit["window"])
		frappe.local.rate_limiter.apply()


def update():
	if hasattr(frappe.local, "rate_limiter"):
		frappe.local.rate_limiter.update()


def respond():
	if hasattr(frappe.local, "rate_limiter"):
		return frappe.local.rate_limiter.respond()


class RateLimiter:
	def __init__(self, limit, window):
		self.limit = int(limit * 1000000)
		self.window = window

		self.start = datetime.utcnow()
		timestamp = get_timestamp()

		self.window_number, self.spent = divmod(timestamp, self.window)
		self.key = frappe.cache().make_key("rate-limit-counter-{}".format(self.window_number))
		self.counter = cint(frappe.cache().get(self.key))
		self.remaining = max(self.limit - self.counter, 0)
		self.reset = self.window - self.spent

		self.end = None
		self.duration = None
		self.rejected = False

	def apply(self):
		if self.counter > self.limit:
			self.rejected = True
			self.reject()

	def reject(self):
		raise frappe.TooManyRequestsError

	def update(self):
		self.end = datetime.utcnow()
		self.duration = int((self.end - self.start).total_seconds() * 1000000)

		pipeline = frappe.cache().pipeline()
		pipeline.incrby(self.key, self.duration)
		pipeline.expire(self.key, self.window)
		pipeline.execute()

	def headers(self):
		headers = {
			"X-RateLimit-Reset": self.reset,
			"X-RateLimit-Limit": self.limit,
			"X-RateLimit-Remaining": self.remaining,
		}
		if self.rejected:
			headers["Retry-After"] = self.reset
		else:
			headers["X-RateLimit-Used"] = self.duration

		return headers

	def respond(self):
		if self.rejected:
			return Response(_("Too Many Requests"), status=429)


def get_timestamp():
	now = frappe.utils.now_datetime()
	epoch = datetime(1970, 1, 1)
	epoch = frappe.utils.convert_utc_to_user_timezone(epoch).replace(tzinfo=None)
	timestamp = int((now - epoch).total_seconds())
	return timestamp
