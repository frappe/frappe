import frappe
from frappe import _

DIRECTIVES = [
	"default-src",
	"script-src",
	"style-src",
	"img-src",
	"connect-src",
	"font-src",
	"object-src",
	"media-src",
	"frame-src",
	"form-action",
	"frame-ancestors",
	"base-uri",
	"manifest-src",
	"worker-src",
	"prefetch-src",
	"upgrade-insecure-requests",
	"block-all-mixed-content",
	"report-uri",
	"report-to",
]


def check(directives: list[dict[str, int | str]] | None = None):
	for directive in directives or []:
		directive_key = directive.get("directive")
		if directive_key not in DIRECTIVES:
			frappe.throw(_("Invalid CSP directive: {0}").format(directive_key))
