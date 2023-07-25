from unittest.mock import patch

import frappe
from frappe import get_hooks
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request
from frappe.website.page_renderers.static_page import StaticPage
from frappe.website.serve import get_response, get_response_content
from frappe.website.utils import build_response, clear_website_cache, get_home_page


class TestWebsite(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Guest")

	def tearDown(self):
		frappe.db.delete("Access Log")
		frappe.set_user("Administrator")

	def test_home_page(self):
		frappe.set_user("Administrator")
		# test home page via role
		user = frappe.get_doc(
			dict(doctype="User", email="test-user-for-home-page@example.com", first_name="test")
		).insert(ignore_if_duplicate=True)
		user.reload()

		role = frappe.get_doc(
			dict(
				doctype="Role",
				role_name="home-page-test",
				desk_access=0,
			)
		).insert(ignore_if_duplicate=True)

		user.add_roles(role.name)
		user.save()

		frappe.db.set_value("Role", "home-page-test", "home_page", "home-page-test")
		frappe.set_user("test-user-for-home-page@example.com")
		self.assertEqual(get_home_page(), "home-page-test")

		frappe.set_user("Administrator")
		frappe.db.set_value("Role", "home-page-test", "home_page", "")

		# home page via portal settings
		frappe.db.set_value("Portal Settings", None, "default_portal_home", "test-portal-home")

		frappe.set_user("test-user-for-home-page@example.com")
		frappe.cache().hdel("home_page", frappe.session.user)
		self.assertEqual(get_home_page(), "test-portal-home")

		frappe.db.set_value("Portal Settings", None, "default_portal_home", "")
		clear_website_cache()

		# home page via website settings
		frappe.db.set_value("Website Settings", None, "home_page", "contact")
		self.assertEqual(get_home_page(), "contact")

		frappe.db.set_value("Website Settings", None, "home_page", None)
		clear_website_cache()

		# fallback homepage
		self.assertEqual(get_home_page(), "me")

		# fallback homepage for guest
		frappe.set_user("Guest")
		self.assertEqual(get_home_page(), "login")
		frappe.set_user("Administrator")

		# test homepage via hooks
		clear_website_cache()
		with patch.object(
			frappe,
			"get_hooks",
			patched_get_hooks(
				"get_website_user_home_page", ["frappe.www._test._test_home_page.get_website_user_home_page"]
			),
		):
			self.assertEqual(get_home_page(), "_test/_test_folder")

		clear_website_cache()
		with patch.object(frappe, "get_hooks", patched_get_hooks("website_user_home_page", ["login"])):
			self.assertEqual(get_home_page(), "login")

		clear_website_cache()
		with patch.object(frappe, "get_hooks", patched_get_hooks("home_page", ["about"])):
			self.assertEqual(get_home_page(), "about")

		clear_website_cache()
		with patch.object(
			frappe, "get_hooks", patched_get_hooks("role_home_page", {"home-page-test": ["home-page-test"]})
		):
			self.assertEqual(get_home_page(), "home-page-test")

	def test_page_load(self):
		set_request(method="POST", path="login")
		response = get_response()

		self.assertEqual(response.status_code, 200)

		html = frappe.safe_decode(response.get_data())

		self.assertTrue("// login.js" in html)
		self.assertTrue("<!-- login.html -->" in html)

	def test_static_page(self):
		set_request(method="GET", path="/_test/static-file-test.png")
		response = get_response()
		self.assertEqual(response.status_code, 200)

		set_request(method="GET", path="/_test/assets/image.jpg")
		response = get_response()
		self.assertEqual(response.status_code, 200)

		set_request(method="GET", path="/_test/assets/image")
		response = get_response()
		self.assertEqual(response.status_code, 200)

		with patch.object(StaticPage, "render") as static_render:
			set_request(method="GET", path="/_test/assets/image")
			response = get_response()
			static_render.assert_called()

	def test_error_page(self):
		set_request(method="GET", path="/_test/problematic_page")
		response = get_response()
		self.assertEqual(response.status_code, 417)

	def test_login(self):
		set_request(method="GET", path="/login")
		response = get_response()
		self.assertEqual(response.status_code, 200)

		html = frappe.safe_decode(response.get_data())

		self.assertTrue("// login.js" in html)
		self.assertTrue("<!-- login.html -->" in html)

	def test_app(self):
		frappe.set_user("Administrator")
		set_request(method="GET", path="/app")
		response = get_response()
		self.assertEqual(response.status_code, 200)

		html = frappe.safe_decode(response.get_data())
		self.assertTrue("window.app = true;" in html)
		frappe.local.session_obj = None

	def test_not_found(self):
		set_request(method="GET", path="/_test/missing")
		response = get_response()
		self.assertEqual(response.status_code, 404)

	def test_redirect(self):
		import frappe.hooks

		frappe.set_user("Administrator")

		frappe.hooks.website_redirects = [
			dict(source=r"/testfrom", target=r"://testto1"),
			dict(source=r"/testfromregex.*", target=r"://testto2"),
			dict(source=r"/testsub/(.*)", target=r"://testto3/\1"),
			dict(
				source=r"/courses/course\?course=(.*)", target=r"/courses/\1", match_with_query_string=True
			),
		]

		website_settings = frappe.get_doc("Website Settings")
		website_settings.append("route_redirects", {"source": "/testsource", "target": "/testtarget"})
		website_settings.save()

		set_request(method="GET", path="/testfrom")
		response = get_response()
		self.assertEqual(response.status_code, 301)
		self.assertEqual(response.headers.get("Location"), r"://testto1")

		set_request(method="GET", path="/testfromregex/test")
		response = get_response()
		self.assertEqual(response.status_code, 301)
		self.assertEqual(response.headers.get("Location"), r"://testto2")

		set_request(method="GET", path="/testsub/me")
		response = get_response()
		self.assertEqual(response.status_code, 301)
		self.assertEqual(response.headers.get("Location"), r"://testto3/me")

		set_request(method="GET", path="/test404")
		response = get_response()
		self.assertEqual(response.status_code, 404)

		set_request(method="GET", path="/testsource")
		response = get_response()
		self.assertEqual(response.status_code, 301)
		self.assertEqual(response.headers.get("Location"), "/testtarget")

		set_request(method="GET", path="/courses/course?course=data")
		response = get_response()
		self.assertEqual(response.status_code, 301)
		self.assertEqual(response.headers.get("Location"), "/courses/data")

		delattr(frappe.hooks, "website_redirects")
		frappe.cache().delete_key("app_hooks")

	def test_custom_page_renderer(self):
		from frappe import get_hooks

		def patched_get_hooks(*args, **kwargs):
			return_value = get_hooks(*args, **kwargs)
			if args and args[0] == "page_renderer":
				return_value = ["frappe.tests.test_website.CustomPageRenderer"]
			return return_value

		with patch.object(frappe, "get_hooks", patched_get_hooks):
			set_request(method="GET", path="/custom")
			response = get_response()
			self.assertEqual(response.status_code, 3984)

			set_request(method="GET", path="/new")
			content = get_response_content()
			self.assertIn("<div>Custom Page Response</div>", content)

			set_request(method="GET", path="/random")
			response = get_response()
			self.assertEqual(response.status_code, 404)

	def test_printview_page(self):
		frappe.db.value_cache[("DocType", "Language", "name")] = (("Language",),)
		frappe.set_user("Administrator")
		content = get_response_content("/Language/ru")
		self.assertIn('<div class="print-format">', content)
		self.assertIn("<div>Language</div>", content)

	def test_custom_base_template_path(self):
		content = get_response_content("/_test/_test_folder/_test_page")
		# assert the text in base template is rendered
		self.assertIn("<h1>This is for testing</h1>", content)

		# assert template block rendered
		self.assertIn("<p>Test content</p>", content)

	def test_json_sidebar_data(self):
		frappe.flags.look_for_sidebar = False
		content = get_response_content("/_test/_test_folder/_test_page")
		self.assertNotIn("Test Sidebar", content)
		clear_website_cache()
		frappe.flags.look_for_sidebar = True
		content = get_response_content("/_test/_test_folder/_test_page")
		self.assertIn("Test Sidebar", content)
		frappe.flags.look_for_sidebar = False

	def test_base_template(self):
		content = get_response_content("/_test/_test_custom_base.html")

		# assert the text in base template is rendered
		self.assertIn("<h1>This is for testing</h1>", content)

		# assert template block rendered
		self.assertIn("<p>Test content</p>", content)

	def test_index_and_next_comment(self):
		content = get_response_content("/_test/_test_folder")
		# test if {index} was rendered
		self.assertIn('<a href="/_test/_test_folder/_test_page"> Test Page</a>', content)

		self.assertIn('<a href="/_test/_test_folder/_test_toc">Test TOC</a>', content)

		content = get_response_content("/_test/_test_folder/_test_page")
		# test if {next} was rendered
		self.assertIn(
			'Next: <a class="btn-next" href="/_test/_test_folder/_test_toc">Test TOC</a>', content
		)

	def test_colocated_assets(self):
		content = get_response_content("/_test/_test_folder/_test_page")
		self.assertIn("""<script>console.log("test data");\n</script>""", content)
		self.assertIn("background-color: var(--bg-color);", content)

	def test_raw_assets_are_loaded(self):
		content = get_response_content("/_test/assets/js_asset.min.js")
		# minified js files should not be passed through jinja renderer
		self.assertEqual("""//{% if title %} {{title}} {% endif %}\nconsole.log("in");\n""", content)

		content = get_response_content("/_test/assets/css_asset.css")
		self.assertEqual("""body{color:red}""", content)

	def test_breadcrumbs(self):
		content = get_response_content("/_test/_test_folder/_test_page")
		self.assertIn('<span itemprop="name">Test Folder</span>', content)
		self.assertIn('<span itemprop="name"> Test Page</span>', content)

		content = get_response_content("/_test/_test_folder/index")
		self.assertIn('<span itemprop="name"> Test</span>', content)
		self.assertIn('<span itemprop="name">Test Folder</span>', content)

	def test_get_context_without_context_object(self):
		content = get_response_content("/_test/_test_no_context")
		self.assertIn("Custom Content", content)

	def test_caching(self):
		# to enable caching
		frappe.flags.force_website_cache = True

		clear_website_cache()
		# first response no-cache
		response = get_response("/_test/_test_folder/_test_page")
		self.assertIn(("X-From-Cache", "False"), list(response.headers))

		# first response returned from cache
		response = get_response("/_test/_test_folder/_test_page")
		self.assertIn(("X-From-Cache", "True"), list(response.headers))

		frappe.flags.force_website_cache = False

	def test_safe_render(self):
		content = get_response_content("/_test/_test_safe_render_on")
		self.assertNotIn("Safe Render On", content)
		self.assertIn("frappe.exceptions.ValidationError: Illegal template", content)

		content = get_response_content("/_test/_test_safe_render_off")
		self.assertIn("Safe Render Off", content)
		self.assertIn("test.__test", content)
		self.assertNotIn("frappe.exceptions.ValidationError: Illegal template", content)

	def test_never_render(self):
		from pathlib import Path
		from random import choices

		WWW = Path(frappe.get_app_path("frappe")) / "www"
		FILES_TO_SKIP = choices(list(WWW.glob("**/*.py*")), k=10)

		for suffix in FILES_TO_SKIP:
			content = get_response_content(suffix.relative_to(WWW))
			self.assertIn("404", content)

	def test_metatags(self):
		content = get_response_content("/_test/_test_metatags")
		self.assertIn('<meta name="title" content="Test Title Metatag">', content)
		self.assertIn('<meta name="description" content="Test Description for Metatag">', content)

	def test_resolve_class(self):
		from frappe.utils.jinja_globals import resolve_class

		context = frappe._dict(primary=True)
		self.assertEqual(resolve_class("test"), "test")
		self.assertEqual(resolve_class("test", "test-2"), "test test-2")
		self.assertEqual(resolve_class("test", {"test-2": False, "test-3": True}), "test test-3")
		self.assertEqual(
			resolve_class(["test1", "test2", context.primary and "primary"]), "test1 test2 primary"
		)

		content = '<a class="{{ resolve_class("btn btn-default", primary and "btn-primary") }}">Test</a>'
		self.assertEqual(
			frappe.render_template(content, context), '<a class="btn btn-default btn-primary">Test</a>'
		)

	def test_app_include(self):
		from frappe import get_hooks

		def patched_get_hooks(*args, **kwargs):
			return_value = get_hooks(*args, **kwargs)
			if isinstance(return_value, dict) and "app_include_js" in return_value:
				return_value.app_include_js.append("test_app_include.js")
				return_value.app_include_css.append("test_app_include.css")
			return return_value

		with patch.object(frappe, "get_hooks", patched_get_hooks):
			frappe.set_user("Administrator")
			frappe.hooks.app_include_js.append("test_app_include.js")
			frappe.hooks.app_include_css.append("test_app_include.css")
			frappe.conf.update({"app_include_js": ["test_app_include_via_site_config.js"]})
			frappe.conf.update({"app_include_css": ["test_app_include_via_site_config.css"]})

			set_request(method="GET", path="/app")
			content = get_response_content("/app")
			self.assertIn('<script type="text/javascript" src="/test_app_include.js"></script>', content)
			self.assertIn(
				'<script type="text/javascript" src="/test_app_include_via_site_config.js"></script>', content
			)
			self.assertIn('<link type="text/css" rel="stylesheet" href="/test_app_include.css">', content)
			self.assertIn(
				'<link type="text/css" rel="stylesheet" href="/test_app_include_via_site_config.css">', content
			)
			delattr(frappe.local, "request")
			frappe.set_user("Guest")


def patched_get_hooks(hook, value):
	def wrapper(*args, **kwargs):
		return_value = get_hooks(*args, **kwargs)
		if args[0] == hook:
			return_value = value
		return return_value

	return wrapper


class CustomPageRenderer:
	def __init__(self, path, status_code=None):
		self.path = path
		# custom status code
		self.status_code = 3984

	def can_render(self):
		if self.path in ("new", "custom"):
			return True

	def render(self):
		return build_response(self.path, """<div>Custom Page Response</div>""", self.status_code)
