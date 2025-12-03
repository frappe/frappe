import frappe
import frappe.utils
from frappe.security.doctype.security_settings.security_settings import get_security_settings
from frappe.utils import caching

DEFAULT_DIRECTIVES = [
	{
		"enabled": 1,
		"directive": "script-src",
		"value": "'self' 'unsafe-eval' 'unsafe-inline'",
	},
	{
		"enabled": 1,
		"directive": "style-src",
		"value": "'self' 'unsafe-inline'",
	},
	{
		"enabled": 1,
		"directive": "font-src",
		"value": "'self'",
	},
]


@caching.site_cache()
def get_directives():
	directives = get_security_settings("csp_directives") or []
	directives = [d for d in directives if d.get("enabled")]
	if len(directives) > 0:
		return directives
	return DEFAULT_DIRECTIVES


@caching.site_cache()
def get_reporting_uri():
	reporting_url = get_security_settings("csp_reporting_url")
	method = "/api/method/frappe.utils.security.csp_report"
	return reporting_url or frappe.utils.get_url() + method


@caching.site_cache()
def get_header_key():
	if get_security_settings("csp_reporting_only"):
		return "Content-Security-Policy-Report-Only"
	return "Content-Security-Policy"


@caching.site_cache()
def get_reporting_headers():
	header = "Reporting-Endpoints"
	value = f'csp-endpoint="{get_reporting_uri()}"'
	return {header: value}


def to_string(directives: list[dict[str, int | str]]) -> str:
	"""
	Convert list of directives to string.

	:param directives: List of directives
	:return: String representation of directives
	"""
	directive_strings = []
	for directive in directives:
		enabled = directive.get("enabled")
		directive_key = directive.get("directive")
		value = directive.get("value")
		if enabled and directive_key and value:
			directive_str = str(directive_key) + " " + str(value)
			directive_strings.append(directive_str)
	return "; ".join(directive_strings)


@caching.site_cache()
def headers():
	enabled = get_security_settings("csp_enabled")
	if not enabled:
		return {}

	directives = get_directives()
	enable_reporting = get_security_settings("csp_enable_reporting")
	reporting_uri = get_reporting_uri()

	if enable_reporting:
		directives.extend(
			[
				{
					"enabled": 1,
					"directive": "report-to",
					"value": "csp-endpoint",
				},
				{
					"enabled": 1,
					"directive": "report-uri",
					"value": reporting_uri,
				},
			]
		)

	return {
		**get_reporting_headers(),
		get_header_key(): to_string(directives),
	}
