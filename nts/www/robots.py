import nts

base_template_path = "www/robots.txt"


def get_context(context):
	robots_txt = (
		nts.db.get_single_value("Website Settings", "robots_txt")
		or (nts.local.conf.robots_txt and nts.read_file(nts.local.conf.robots_txt))
		or ""
	)

	return {"robots_txt": robots_txt}
