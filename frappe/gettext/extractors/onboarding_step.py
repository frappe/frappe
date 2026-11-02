import json

from .utils import get_line_number


def extract(fileobj, *args, **kwargs):
	"""
	Extract messages from Onboarding Step JSON files.

	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	text = fileobj.read().decode()
	data = json.loads(text)

	if isinstance(data, list):
		return

	if data.get("doctype") != "Onboarding Step":
		return

	step_title = data.get("title")

	yield get_line_number(text, "title", step_title), "_", step_title, ["Title of an Onboarding Step"]

	if action_label := data.get("action_label"):
		yield (
			get_line_number(text, "action_label", action_label),
			"_",
			action_label,
			[f"Label of an action in the Onboarding Step '{step_title}'"],
		)

	if description := data.get("description"):
		yield (
			get_line_number(text, "description", description),
			"_",
			description,
			[f"Description of the Onboarding Step '{step_title}'"],
		)

	if report_description := data.get("report_description"):
		yield (
			get_line_number(text, "report_description", report_description),
			"_",
			report_description,
			[f"Description of a report in the Onboarding Step '{step_title}'"],
		)
