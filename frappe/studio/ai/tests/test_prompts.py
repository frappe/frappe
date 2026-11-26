from frappe.studio.ai.prompts import get_generation_prompt, get_system_prompt_for_mode
from frappe.tests import IntegrationTestCase


class TestPrompts(IntegrationTestCase):
	def test_every_prompt_carries_the_skill_rules(self):
		"""Each prompt reads its runtime, design and routing rules from the studio-app-building
		skill, so renaming or moving one of those files breaks the prompt."""
		prompts = [
			get_system_prompt_for_mode(False),
			get_system_prompt_for_mode(True),
			get_generation_prompt(),
		]
		for prompt in prompts:
			self.assertIn("# Runtime rules", prompt)
			self.assertIn("# Designing Studio pages", prompt)
			# the f-string must not touch a binding token
			self.assertIn("{{ expression }}", prompt)
		for prompt in prompts[:2]:
			self.assertIn("# Routing and boot data", prompt)
			self.assertIn("extendRoute(route)", prompt)
