import json

from .utils import get_line_number


def extract(fileobj, *args, **kwargs):
	"""
	Extract messages from Module Onboarding JSON files.

	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	text = fileobj.read().decode()
	data = json.loads(text)

	if isinstance(data, list):
		return

	if data.get("doctype") != "Module Onboarding":
		return

	onboarding_name = data.get("name")

	if title := data.get("title"):
		yield (
			get_line_number(text, "title", title),
			"_",
			title,
			[f"Title of the Module Onboarding '{onboarding_name}'"],
		)

	if subtitle := data.get("subtitle"):
		yield (
			get_line_number(text, "subtitle", subtitle),
			"_",
			subtitle,
			[f"Subtitle of the Module Onboarding '{onboarding_name}'"],
		)

	if success_message := data.get("success_message"):
		yield (
			get_line_number(text, "success_message", success_message),
			"_",
			success_message,
			[f"Success message of the Module Onboarding '{onboarding_name}'"],
		)
