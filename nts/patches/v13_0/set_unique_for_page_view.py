import nts


def execute():
	nts.reload_doc("website", "doctype", "web_page_view", force=True)
	site_url = nts.utils.get_site_url(nts.local.site)
	nts.db.sql(f"""UPDATE `tabWeb Page View` set is_unique=1 where referrer LIKE '%{site_url}%'""")
