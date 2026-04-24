"""
Unit tests for frappe.parallel_test_runner

Specifically tests the orchestrator HTTP call timeout and connection error
handling added to prevent indefinite CI hangs.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch


class TestCallOrchestrator(unittest.TestCase):
	"""Tests for ParallelTestWithOrchestrator.call_orchestrator()"""

	def _make_runner(self):
		"""Return a ParallelTestWithOrchestrator instance without running __init__."""
		from frappe.parallel_test_runner import ParallelTestWithOrchestrator

		runner = object.__new__(ParallelTestWithOrchestrator)
		runner.orchestrator_url = "http://orchestrator.test"
		runner.ci_build_id = "build-123"
		runner.ci_instance_id = "inst-456"
		return runner

	# ------------------------------------------------------------------
	# Happy path
	# ------------------------------------------------------------------

	def test_successful_json_response(self):
		"""call_orchestrator returns parsed JSON on a successful response."""
		import requests

		runner = self._make_runner()

		mock_response = MagicMock()
		mock_response.headers = {"content-type": "application/json"}
		mock_response.json.return_value = {"status": "ok", "next_test": "test_foo.py"}
		mock_response.raise_for_status.return_value = None

		with patch.object(requests, "get", return_value=mock_response) as mock_get:
			result = runner.call_orchestrator("get-next-test-spec")

		mock_get.assert_called_once()
		_args, kwargs = mock_get.call_args
		self.assertEqual(kwargs["timeout"], (runner.ORCHESTRATOR_CONNECT_TIMEOUT, runner.ORCHESTRATOR_READ_TIMEOUT))
		self.assertEqual(result, {"status": "ok", "next_test": "test_foo.py"})

	def test_successful_non_json_response(self):
		"""call_orchestrator returns empty dict for non-JSON responses."""
		import requests

		runner = self._make_runner()

		mock_response = MagicMock()
		mock_response.headers = {"content-type": "text/plain"}
		mock_response.raise_for_status.return_value = None

		with patch.object(requests, "get", return_value=mock_response):
			result = runner.call_orchestrator("register-instance")

		self.assertEqual(result, {})

	# ------------------------------------------------------------------
	# Timeout handling
	# ------------------------------------------------------------------

	def test_timeout_on_test_completed_warns_and_returns_empty(self):
		"""A timeout on 'test-completed' must NOT call sys.exit – return {} instead."""
		import requests

		runner = self._make_runner()

		with patch.object(requests, "get", side_effect=requests.exceptions.Timeout), \
			 patch.object(sys, "exit") as mock_exit:
			result = runner.call_orchestrator("test-completed")

		mock_exit.assert_not_called()
		self.assertEqual(result, {})

	def test_timeout_on_register_instance_exits(self):
		"""A timeout on 'register-instance' must call sys.exit(1)."""
		import requests

		runner = self._make_runner()

		with patch.object(requests, "get", side_effect=requests.exceptions.Timeout), \
			 patch.object(sys, "exit") as mock_exit:
			runner.call_orchestrator("register-instance")

		mock_exit.assert_called_once_with(1)

	def test_timeout_on_get_next_test_spec_exits(self):
		"""A timeout on 'get-next-test-spec' must call sys.exit(1)."""
		import requests

		runner = self._make_runner()

		with patch.object(requests, "get", side_effect=requests.exceptions.Timeout), \
			 patch.object(sys, "exit") as mock_exit:
			runner.call_orchestrator("get-next-test-spec")

		mock_exit.assert_called_once_with(1)

	# ------------------------------------------------------------------
	# Connection error handling
	# ------------------------------------------------------------------

	def test_connection_error_on_test_completed_warns_and_returns_empty(self):
		"""A ConnectionError on 'test-completed' must NOT call sys.exit – return {} instead."""
		import requests

		runner = self._make_runner()

		with patch.object(requests, "get", side_effect=requests.exceptions.ConnectionError("refused")), \
			 patch.object(sys, "exit") as mock_exit:
			result = runner.call_orchestrator("test-completed")

		mock_exit.assert_not_called()
		self.assertEqual(result, {})

	def test_connection_error_on_register_instance_exits(self):
		"""A ConnectionError on 'register-instance' must call sys.exit(1)."""
		import requests

		runner = self._make_runner()

		with patch.object(requests, "get", side_effect=requests.exceptions.ConnectionError("refused")), \
			 patch.object(sys, "exit") as mock_exit:
			runner.call_orchestrator("register-instance")

		mock_exit.assert_called_once_with(1)

	# ------------------------------------------------------------------
	# Timeout constants sanity check
	# ------------------------------------------------------------------

	def test_timeout_constants_are_positive(self):
		from frappe.parallel_test_runner import ParallelTestWithOrchestrator

		self.assertGreater(ParallelTestWithOrchestrator.ORCHESTRATOR_CONNECT_TIMEOUT, 0)
		self.assertGreater(ParallelTestWithOrchestrator.ORCHESTRATOR_READ_TIMEOUT, 0)

	def test_timeout_passed_to_requests_get(self):
		"""Verify the exact timeout tuple is forwarded to requests.get."""
		import requests

		runner = self._make_runner()

		mock_response = MagicMock()
		mock_response.headers = {"content-type": "text/plain"}
		mock_response.raise_for_status.return_value = None

		with patch.object(requests, "get", return_value=mock_response) as mock_get:
			runner.call_orchestrator("get-next-test-spec")

		_args, kwargs = mock_get.call_args
		expected_timeout = (
			runner.ORCHESTRATOR_CONNECT_TIMEOUT,
			runner.ORCHESTRATOR_READ_TIMEOUT,
		)
		self.assertEqual(kwargs["timeout"], expected_timeout)


if __name__ == "__main__":
	unittest.main()
