# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import unittest
from importlib.metadata import requires, version

from packaging.requirements import Requirement
from packaging.version import Version


class TestDependencyCompat(unittest.TestCase):
	def test_cryptography_pyopenssl_compatible(self):
		"""pyOpenSSL pins a range of compatible `cryptography` versions.

		Pip does not re-resolve already-satisfied transitive deps when other packages
		are upgraded, so it's possible to end up with an installed `cryptography` that
		pyOpenSSL doesn't actually support. Verify the installed version satisfies
		pyOpenSSL's own declared requirement, using package metadata as source of truth.
		"""
		crypto_reqs = [
			req for r in (requires("pyOpenSSL") or []) if (req := Requirement(r)).name == "cryptography"
		]
		self.assertTrue(crypto_reqs, "pyOpenSSL does not declare a cryptography requirement")
		crypto_req = crypto_reqs[0]

		installed = Version(version("cryptography"))
		self.assertIn(
			installed,
			crypto_req.specifier,
			f"Installed cryptography {installed} is incompatible with pyOpenSSL's requirement '{crypto_req}'",
		)
