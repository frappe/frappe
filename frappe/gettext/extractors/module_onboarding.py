import json


def extract(fileobj, *args, **kwargs):
	"""
	Extract messages from Module Onboarding JSON files.

	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	data = json.load(fileobj)

	if isinstance(data, list):
		return

	if data.get("doctype") != "Module Onboarding":
		return

	onboarding_name = data.get("name")

	if title := data.get("title"):
		yield None, "_", title, [f"Title of the Module Onboarding '{onboarding_name}'"]

	if subtitle := data.get("subtitle"):
		yield None, "_", subtitle, [f"Subtitle of the Module Onboarding '{onboarding_name}'"]

	if success_message := data.get("success_message"):
		yield None, "_", success_message, [f"Success message of the Module Onboarding '{onboarding_name}'"]
