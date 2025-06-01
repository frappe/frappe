import nts


def execute():
	nts.reload_doc("website", "doctype", "web_page_view", force=True)
	nts.db.sql("""UPDATE `tabWeb Page View` set path='/' where path=''""")
