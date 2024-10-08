import logging

from .integration_test_case import IntegrationTestCase

logger = logging.Logger(__file__)


class MockedRequestTestCase(IntegrationTestCase):
	def setUp(self):
		import responses

		self.responses = responses.RequestsMock()
		self.responses.start()

		self.addCleanup(self.responses.stop)
		self.addCleanup(self.responses.reset)

		return super().setUp()
