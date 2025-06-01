import nts


def execute():
	nts.reload_doc("core", "doctype", "domain")
	nts.reload_doc("core", "doctype", "has_domain")
	active_domains = nts.get_active_domains()
	all_domains = nts.get_all("Domain")

	for d in all_domains:
		if d.name not in active_domains:
			inactive_domain = nts.get_doc("Domain", d.name)
			inactive_domain.setup_data()
			inactive_domain.remove_custom_field()
