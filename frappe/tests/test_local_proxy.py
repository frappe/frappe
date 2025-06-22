import time
from threading import Thread

import frappe
from frappe.tests import IntegrationTestCase

# Note: These tests are adapted from official tests: https://github.com/pallets/werkzeug/blob/main/tests/test_local.py
# We use them to check if our overrides of localproxy work fine.
# Reused under BSD 3 clause license: https://github.com/pallets/werkzeug/blob/main/LICENSE.txt


class TestFrappeLocal(IntegrationTestCase):
	def test_basic_local(self):
		ns = frappe.local
		ns.foo = 0
		values = []

		def value_setter(idx):
			time.sleep(0.01 * idx)
			ns.foo = idx
			time.sleep(0.02)
			values.append(ns.foo)

		threads = [Thread(target=value_setter, args=(x,)) for x in [1, 2, 3]]
		for thread in threads:
			thread.start()
		for thread in threads:
			thread.join()
		assert sorted(values) == [1, 2, 3]

		def delfoo():
			del ns.foo

		delfoo()
		self.assertRaises(AttributeError, lambda: ns.foo)
		self.assertRaises(AttributeError, delfoo)

	def test_proxy_local(self):
		ns = frappe.local
		ns.foo = []
		p = ns("foo")
		p.append(42)
		p.append(23)
		p[1:] = [1, 2, 3]
		assert p == [42, 1, 2, 3]
		assert p == ns.foo
		ns.foo += [1]
		assert list(p) == [42, 1, 2, 3, 1]
		p_from_local = ns("foo")
		p_from_local.append(2)
		assert p == p_from_local
		assert p._get_current_object() is ns.foo
