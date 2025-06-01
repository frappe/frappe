import nts


def execute():
	providers = nts.get_all("Social Login Key")

	for provider in providers:
		doc = nts.get_doc("Social Login Key", provider)
		doc.set_icon()
		doc.save()
