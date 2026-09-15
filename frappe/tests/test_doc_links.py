import re
import unittest
from pathlib import Path

import requests

import frappe

# Files that embed documentation URLs in user-facing error messages. A dead link here
# is worse than no link: the user hits an error, clicks for help, and gets a 404.
SOURCES_WITH_DOC_LINKS = ("public/js/frappe/request.js",)

DOC_LINK_PATTERN = re.compile(r"https://docs\.frappe\.io/[^\s\"'`<>)]+")


class TestDocumentationLinks(unittest.TestCase):
	def test_doc_links_in_error_messages_resolve(self):
		app_path = Path(frappe.get_app_path("frappe"))

		urls = set()
		for source in SOURCES_WITH_DOC_LINKS:
			urls.update(DOC_LINK_PATTERN.findall((app_path / source).read_text()))

		self.assertTrue(urls, "no documentation links found, has the pattern or path drifted?")

		for url in sorted(urls):
			with self.subTest(url=url):
				try:
					# redirects are fine, docs pages get reorganised; a 404 is not
					response = requests.get(url, timeout=30, allow_redirects=True)
				except requests.RequestException as e:
					raise unittest.SkipTest(f"could not reach {url}: {e}")

				self.assertLess(
					response.status_code,
					400,
					f"{url} is dead (HTTP {response.status_code}), update or remove the link",
				)
