import frappe
from frappe.studio.build import get_editor_assets
from frappe.utils import cint

no_cache = 1


def get_context(context):
	csrf_token = frappe.sessions.get_csrf_token()
	frappe.db.commit()  # nosemgrep
	context.csrf_token = csrf_token
	context.site_url = get_site_url()
	context.site_name = frappe.local.site
	context.is_developer_mode = cint(frappe.conf.developer_mode)
	context.assets = get_editor_assets("index.html")


@frappe.whitelist(methods=["POST"], allow_guest=True)  # nosemgrep: guest-whitelisted-method
def get_context_for_dev():
	if not frappe.conf.developer_mode:
		frappe.throw(frappe._("This method is only meant for developer mode"))
	return frappe._dict(
		{
			"site_url": get_site_url(),
			"site_name": frappe.local.site,
			"is_developer_mode": cint(frappe.conf.developer_mode),
		}
	)


def get_site_url() -> str:
	return frappe.utils.get_site_url(frappe.local.site)
