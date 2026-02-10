import random
from string import printable
from time import time
from unittest import TestCase

import orjson
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from frappe.utils.password_strength import _clamp_large_ints, test_password_strength


class TestPasswordStrength(TestCase):
	@retry(
		retry=retry_if_exception_type(AssertionError),
		stop=stop_after_attempt(3),
		wait=wait_fixed(0.5),
		reraise=True,
	)
	def test_long_password(self):
		password = "".join(random.choice(printable) for _ in range(600))

		start_second = time()
		result = test_password_strength(password)
		end_second = time()

		self.assertLess(end_second - start_second, 10)
		self.assertIn("feedback", result)

	def test_result_is_orjson_serializable(self):
		"""zxcvbn can return integers exceeding 64-bit range which orjson cannot serialize."""
		result = test_password_strength("Eastern_43A1W")
		# should not raise TypeError: Integer exceeds 64-bit range
		orjson.dumps(result)

	def test_clamp_large_ints(self):
		INT64_MAX = 2**63 - 1
		data = {
			"guesses": 10**100,
			"score": 4,
			"flag": True,
			"nested": {"big": 2**64, "ok": 42},
			"items": [10**100, 1, False],
		}
		_clamp_large_ints(data)

		self.assertEqual(data["guesses"], INT64_MAX)
		self.assertEqual(data["score"], 4)
		self.assertIs(data["flag"], True)
		self.assertEqual(data["nested"]["big"], INT64_MAX)
		self.assertEqual(data["nested"]["ok"], 42)
		self.assertEqual(data["items"][0], INT64_MAX)
		self.assertEqual(data["items"][1], 1)
		self.assertIs(data["items"][2], False)
