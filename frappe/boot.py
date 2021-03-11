# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

from six import iteritems, text_type

"""
bootstrap client session
"""

import frappe
import frappe.defaults
import frappe.desk.desk_page
from frappe.desk.form.load import get_meta_bundle
from frappe.utils.change_log import get_versions
from frappe.translate import get_lang_dict
from frappe.email.inbox import get_email_accounts
from frappe.social.doctype.energy_point_settings.energy_point_settings import is_energy_point_enabled
from frappe.website.doctype.web_page_view.web_page_view import is_tracking_enabled
from frappe.social.doctype.energy_point_log.energy_point_log import get_energy_points
from frappe.model.base_document import get_controller
from frappe.social.doctype.post.post import frequently_visited_links
from frappe.core.doctype.navbar_settings.navbar_settings import get_navbar_settings, get_app_logo

def get_bootinfo():
	"""build and return boot info"""
	frappe.set_user_lang(frappe.session.user)
	bootinfo = frappe._dict()
	hooks = frappe.get_hooks()
	doclist = []

	# user
	get_user(bootinfo)

	# system info
	bootinfo.sitename = frappe.local.site
	bootinfo.sysdefaults = frappe.defaults.get_defaults()
	bootinfo.server_date = frappe.utils.nowdate()

	if frappe.session['user'] != 'Guest':
		bootinfo.user_info = get_user_info()
		bootinfo.sid = frappe.session['sid']

	bootinfo.modules = {}
	bootinfo.module_list = []
	load_desktop_data(bootinfo)
	bootinfo.letter_heads = get_letter_heads()
	bootinfo.active_domains = frappe.get_active_domains()
	bootinfo.all_domains = [d.get("name") for d in frappe.get_all("Domain")]
	add_layouts(bootinfo)

	bootinfo.module_app = frappe.local.module_app
	bootinfo.single_types = [d.name for d in frappe.get_all('DocType', {'issingle': 1})]
	bootinfo.nested_set_doctypes = [d.parent for d in frappe.get_all('DocField', {'fieldname': 'lft'}, ['parent'])]
	add_home_page(bootinfo, doclist)
	bootinfo.page_info = get_allowed_pages()
	load_translations(bootinfo)
	add_timezone_info(bootinfo)
	load_conf_settings(bootinfo)
	load_print(bootinfo, doclist)
	doclist.extend(get_meta_bundle("Page"))
	bootinfo.home_folder = frappe.db.get_value("File", {"is_home_folder": 1})
	bootinfo.navbar_settings = get_navbar_settings()
	bootinfo.notification_settings = get_notification_settings()

	# ipinfo
	if frappe.session.data.get('ipinfo'):
		bootinfo.ipinfo = frappe.session['data']['ipinfo']

	# add docs
	bootinfo.docs = doclist

	for method in hooks.boot_session or []:
		frappe.get_attr(method)(bootinfo)

	if bootinfo.lang:
		bootinfo.lang = text_type(bootinfo.lang)
	bootinfo.versions = {k: v['version'] for k, v in get_versions().items()}

	bootinfo.error_report_email = frappe.conf.error_report_email
	bootinfo.calendars = sorted(frappe.get_hooks("calendars"))
	bootinfo.treeviews = frappe.get_hooks("treeviews") or []
	bootinfo.lang_dict = get_lang_dict()
	bootinfo.success_action = get_success_action()
	bootinfo.update(get_email_accounts(user=frappe.session.user))
	bootinfo.energy_points_enabled = is_energy_point_enabled()
	bootinfo.website_tracking_enabled = is_tracking_enabled()
	bootinfo.points = get_energy_points(frappe.session.user)
	bootinfo.frequently_visited_links = frequently_visited_links()
	bootinfo.link_preview_doctypes = get_link_preview_doctypes()
	bootinfo.additional_filters_config = get_additional_filters_from_hooks()
	bootinfo.desk_settings = get_desk_settings()
	bootinfo.app_logo_url = get_app_logo()

	return bootinfo

def get_letter_heads():
	letter_heads = {}
	for letter_head in frappe.get_all("Letter Head", fields = ["name", "content", "footer"]):
		letter_heads.setdefault(letter_head.name,
			{'header': letter_head.content, 'footer': letter_head.footer})

	return letter_heads

def load_conf_settings(bootinfo):
	from frappe import conf
	bootinfo.max_file_size = conf.get('max_file_size') or 10485760
	for key in ('developer_mode', 'socketio_port', 'file_watcher_port'):
		if key in conf: bootinfo[key] = conf.get(key)

def load_desktop_data(bootinfo):
	from frappe.desk.desktop import get_desk_sidebar_items
	bootinfo.allowed_workspaces = get_desk_sidebar_items()
	bootinfo.module_page_map = get_controller("Workspace").get_module_page_map()
	bootinfo.dashboards = frappe.get_all("Dashboard")

def get_allowed_pages(cache=False):
	return get_user_pages_or_reports('Page', cache=cache)

def get_allowed_reports(cache=False):
	return get_user_pages_or_reports('Report', cache=cache)

def get_user_pages_or_reports(parent, cache=False):
	_cache = frappe.cache()

	if cache:
		has_role = _cache.get_value('has_role:' + parent, user=frappe.session.user)
		if has_role:
			return has_role

	roles = frappe.get_roles()
	has_role = {}
	column = get_column(parent)

	# get pages or reports set on custom role
	pages_with_custom_roles = frappe.db.sql("""
		select
			`tabCustom Role`.{field} as name,
			`tabCustom Role`.modified,
			`tabCustom Role`.ref_doctype,
			{column}
		from `tabCustom Role`, `tabHas Role`, `tab{parent}`
		where
			`tabHas Role`.parent = `tabCustom Role`.name
			and `tab{parent}`.name = `tabCustom Role`.{field}
			and `tabCustom Role`.{field} is not null
			and `tabHas Role`.role in ({roles})
	""".format(field=parent.lower(), parent=parent, column=column,
		roles = ', '.join(['%s']*len(roles))), roles, as_dict=1)

	for p in pages_with_custom_roles:
		has_role[p.name] = {"modified":p.modified, "title": p.title, "ref_doctype": p.ref_doctype}

	pages_with_standard_roles = frappe.db.sql("""
		select distinct
			`tab{parent}`.name as name,
			`tab{parent}`.modified,
			{column}
		from `tabHas Role`, `tab{parent}`
		where
			`tabHas Role`.role in ({roles})
			and `tabHas Role`.parent = `tab{parent}`.name
			and `tab{parent}`.`name` not in (
				select `tabCustom Role`.{field} from `tabCustom Role`
				where `tabCustom Role`.{field} is not null)
			{condition}
		""".format(parent=parent, column=column, roles = ', '.join(['%s']*len(roles)),
			field=parent.lower(), condition="and `tabReport`.disabled=0" if parent == "Report" else ""),
			roles, as_dict=True)

	for p in pages_with_standard_roles:
		if p.name not in has_role:
			has_role[p.name] = {"modified":p.modified, "title": p.title}
			if parent == "Report":
				has_role[p.name].update({'ref_doctype': p.ref_doctype})

	# pages with no role are allowed
	if parent =="Page":
		pages_with_no_roles = frappe.db.sql("""
			select
				`tab{parent}`.name, `tab{parent}`.modified, {column}
			from `tab{parent}`
			where
				(select count(*) from `tabHas Role`
				where `tabHas Role`.parent=`tab{parent}`.`name`) = 0
		""".format(parent=parent, column=column), as_dict=1)

		for p in pages_with_no_roles:
			if p.name not in has_role:
				has_role[p.name] = {"modified": p.modified, "title": p.title}

	elif parent == "Report":
		reports = frappe.get_all("Report",
			fields=["name", "report_type"],
			filters={"name": ("in", has_role.keys())},
			ignore_ifnull=True
		)
		for report in reports:
			has_role[report.name]["report_type"] = report.report_type

	# Expire every six hours
	_cache.set_value('has_role:' + parent, has_role, frappe.session.user, 21600)
	return has_role

def get_column(doctype):
	column = "`tabPage`.title as title"
	if doctype == "Report":
		column = "`tabReport`.`name` as title, `tabReport`.ref_doctype, `tabReport`.report_type"

	return column

def load_translations(bootinfo):
	messages = frappe.get_lang_dict("boot")

	bootinfo["lang"] = frappe.lang

	# load translated report names
	for name in bootinfo.user.all_reports:
		messages[name] = frappe._(name)

	# only untranslated
	messages = {k:v for k, v in iteritems(messages) if k!=v}

	bootinfo["__messages"] = messages

def get_user_info():
	user_info = frappe.db.get_all('User', fields=['`name`', 'full_name as fullname', 'user_image as image',
		'gender', 'email', 'username', 'bio', 'location', 'interest', 'banner_image', 'allowed_in_mentions', 'user_type'],
		filters=dict(enabled=1))

	user_info_map = {d.name: d for d in user_info}

	admin_data = user_info_map.get('Administrator')
	if admin_data:
		user_info_map[admin_data.email] = admin_data

	return user_info_map

def get_user(bootinfo):
	"""get user info"""
	bootinfo.user = frappe.get_user().load_user()

def add_home_page(bootinfo, docs):
	"""load home page"""
	if frappe.session.user=="Guest":
		return
	home_page = frappe.db.get_default("desktop:home_page")

	if home_page == "setup-wizard":
		bootinfo.setup_wizard_requires = frappe.get_hooks("setup_wizard_requires")

	try:
		page = frappe.desk.desk_page.get(home_page)
		docs.append(page)
		bootinfo['home_page'] = page.name
	except (frappe.DoesNotExistError, frappe.PermissionError):
		if frappe.message_log:
			frappe.message_log.pop()
		bootinfo['home_page'] = 'Workspaces'

def add_timezone_info(bootinfo):
	system = bootinfo.sysdefaults.get("time_zone")
	import frappe.utils.momentjs
	bootinfo.timezone_info = {"zones":{}, "rules":{}, "links":{}}
	frappe.utils.momentjs.update(system, bootinfo.timezone_info)

def load_print(bootinfo, doclist):
	print_settings = frappe.db.get_singles_dict("Print Settings")
	print_settings.doctype = ":Print Settings"
	doclist.append(print_settings)
	load_print_css(bootinfo, print_settings)

def load_print_css(bootinfo, print_settings):
	import frappe.www.printview
	bootinfo.print_css = frappe.www.printview.get_print_style(print_settings.print_style or "Redesign", for_legacy=True)

def get_unseen_notes():
	return frappe.db.sql('''select `name`, title, content, notify_on_every_login from `tabNote` where notify_on_login=1
		and expire_notification_on > %s and %s not in
			(select user from `tabNote Seen By` nsb
				where nsb.parent=`tabNote`.name)''', (frappe.utils.now(), frappe.session.user), as_dict=True)

def get_success_action():
	return frappe.get_all("Success Action", fields=["*"])

def get_link_preview_doctypes():
	from frappe.utils import cint

	link_preview_doctypes = [d.name for d in frappe.db.get_all('DocType', {'show_preview_popup': 1})]
	customizations = frappe.get_all("Property Setter",
		fields=['doc_type', 'value'],
		filters={'property': 'show_preview_popup'}
	)

	for custom in customizations:
		if not cint(custom.value) and custom.doc_type in link_preview_doctypes:
			link_preview_doctypes.remove(custom.doc_type)
		else:
			link_preview_doctypes.append(custom.doc_type)

	return link_preview_doctypes

def get_additional_filters_from_hooks():
	filter_config = frappe._dict()
	filter_hooks = frappe.get_hooks('filters_config')
	for hook in filter_hooks:
		filter_config.update(frappe.get_attr(hook)())

	return filter_config

def add_layouts(bootinfo):
	# add routes for readable doctypes
	bootinfo.doctype_layouts = frappe.get_all('DocType Layout', ['name', 'route', 'document_type'])

def get_desk_settings():
	role_list = frappe.get_all('Role', fields=['*'], filters=dict(
		name=['in', frappe.get_roles()]
	))
	desk_settings = {}

	from frappe.core.doctype.role.role import desk_properties

	for role in role_list:
		for key in desk_properties:
			desk_settings[key] = desk_settings.get(key) or role.get(key)

	return desk_settings

def get_notification_settings():
	return frappe.get_cached_doc('Notification Settings', frappe.session.user)
