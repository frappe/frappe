import json


def extract(fileobj, *args, **kwargs):
	"""
	Extract messages from Onboarding Step JSON files.

	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	data = json.load(fileobj)

	if isinstance(data, list):
		return

	if data.get("doctype") != "Onboarding Step":
		return

	step_title = data.get("title")

	yield None, "_", step_title, ["Title of an Onboarding Step"]

	if action_label := data.get("action_label"):
		yield None, "_", action_label, [f"Label of an action in the Onboarding Step '{step_title}'"]

	if description := data.get("description"):
		yield None, "_", description, [f"Description of the Onboarding Step '{step_title}'"]

	if report_description := data.get("report_description"):
		yield (
			None,
			"_",
			report_description,
			[f"Description of a report in the Onboarding Step '{step_title}'"],
		)
