from functools import lru_cache

import frappe
from frappe.app import application as _trigger_imports
from frappe.tests.microbenchmarks.utils import NanoBenchmark
from frappe.utils import get_test_client
from frappe.utils.user import AUTOMATIC_ROLES

try:
	from frappe.tests.utils import toggle_test_mode
except ImportError:

	def toggle_test_mode(*args, **kwargs):
		frappe.flags.in_test = True


TEST_USER = "test@example.com"


def request(method, path, data=None, auth=False):
	client = get_test_client()
	headers = {"X-Frappe-Site-Name": get_site()}
	if auth:
		sid = get_sid()
		client.set_cookie("sid", sid)
	return client.open(path, headers=headers, method=method, data=data)


def bench_request_overheads():
	resp = request("GET", "/api/method/ping")
	assert resp.status_code == 200


def bench_request_authed_overheads():
	resp = request("GET", "/api/method/ping", auth=True)
	assert resp.status_code == 200


def bench_request_socketio_auth():
	resp = request("GET", "/api/method/frappe.realtime.get_user_info", auth=True)
	assert resp.status_code == 200


def bench_request_socketio_perm_check():
	resp = request(
		"GET",
		"/api/method/frappe.realtime.has_permission",
		auth=True,
		data={"doctype": "Role", "name": "Guest"},
	)
	assert resp.status_code == 200


def bench_request_getdoc():
	resp = request(
		"POST",
		"/api/method/frappe.desk.form.load.getdoc",
		data={"doctype": "Role", "name": "Guest"},
		auth=True,
	)
	assert resp.status_code == 200


def bench_list_view_count_query():
	resp = request(
		"POST",
		"/api/method/frappe.desk.reportview.get_count",
		data={"doctype": "Role", "filters": "[]", "fields": "[]", "distinct": "false", "limit": "1001"},
		auth=True,
	)
	assert resp.status_code == 200


def bench_login_page_render():
	resp = request("GET", "/login")
	assert resp.status_code == 200


def bench_desk_page_render():
	resp = request("GET", "/desk", auth=True)
	assert resp.status_code == 200


def bench_web_save_doc():
	doc = frappe.get_doc("Gender", "Other").as_dict()
	payload = {"doc": frappe.as_json(doc), "action": "Save"}
	resp = request("POST", "/api/method/frappe.desk.form.save.savedocs", auth=True, data=payload)
	assert resp.status_code == 200


def bench_list_view_query():
	reportview_get_payload = {
		"doctype": "Role",
		"fields": '["`tabRole`.`name`","`tabRole`.`owner`","`tabRole`.`creation`","`tabRole`.`modified`","`tabRole`.`modified_by`" ,"`tabRole`.`_user_tags`","`tabRole`.`_comments`","`tabRole`.`_assign`","`tabRole`.`_liked_by`","`tabRole`.`docstatus`","`tabRole`.`idx`","`tabRole`.`disabled`"]',
		"filters": "[]",
		"order_by": "`tabRole`.creation desc",
		"start": "0",
		"page_length": "20",
		"group_by": "",
		"with_comment_count": "1",
	}
	resp = request("POST", "/api/method/frappe.desk.reportview.get", data=reportview_get_payload, auth=True)
	assert resp.status_code == 200


from frappe import rate_limiter


def bench_rate_limiter():
	"""Simulate everything that rate limiter typically does."""
	frappe.conf.rate_limit = {"limit": 28800000, "window": 86400}
	rate_limiter.apply()
	rate_limiter.update()
	frappe.local.rate_limiter.headers()


@frappe.whitelist()
def type_checked_function(x: int, y: str) -> float:
	return 42.0


bench_request_type_checking = NanoBenchmark(
	"type_checked_function(x=42, y='42')",
	setup="toggle_test_mode(True)",
	globals={"type_checked_function": type_checked_function, "toggle_test_mode": toggle_test_mode},
)


@lru_cache
def get_site():
	return frappe.local.site


@lru_cache
def get_sid():
	from frappe.auth import CookieManager, LoginManager
	from frappe.utils import set_request

	create_test_user(TEST_USER)

	set_request(path="/")
	frappe.local.cookie_manager = CookieManager()
	frappe.local.login_manager = LoginManager()
	frappe.local.login_manager.login_as(TEST_USER)
	frappe.db.commit()
	return frappe.session.sid


def create_test_user(name):
	if frappe.db.exists("User", name):
		return

	user = frappe.new_doc("User")
	user.email = name
	user.first_name = "Frappe"
	user.new_password = frappe.local.conf.admin_password
	user.send_welcome_email = 0
	user.time_zone = "Asia/Kolkata"
	user.flags.ignore_password_policy = True
	user.insert(ignore_if_duplicate=True)

	user.reload()

	all_roles = set(frappe.get_all("Role", pluck="name"))
	for role in all_roles - set(AUTOMATIC_ROLES):
		user.append("roles", {"role": role})
	user.save()
	frappe.db.commit()
