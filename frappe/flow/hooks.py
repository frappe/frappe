app_name = "flow"
app_title = "Flow"
app_publisher = "Shrihari Mahabal"
app_description = "Frappe Flow — native AI agents, tools, and triggers for Frappe"
app_email = "shriharimahabal08@gmail.com"
app_license = "mit"

export_python_type_annotations = True

# The /flow page: a Vite app (frontend/) built by `yarn build` into public/frontend, its
# entry copied to www/flow/index.html. Every path under /flow serves that page.
add_to_apps_screen = [
	{
		"name": "flow",
		"logo": "/assets/flow/frontend/flow.png",
		"title": "Flow",
		"route": "/flow",
		"has_permission": "frappe.flow.permissions.has_app_permission",
	}
]
website_route_rules = [{"from_route": "/flow/<path:app_path>", "to_route": "flow"}]

doc_events = {
	"*": {
		"after_insert": "frappe.flow.triggers.dispatch",
		"on_update": "frappe.flow.triggers.dispatch",
		"on_submit": "frappe.flow.triggers.dispatch",
		"on_cancel": "frappe.flow.triggers.dispatch",
		"on_trash": "frappe.flow.triggers.dispatch",
	},
	# a viewer taken off a chat stops following it live
	"DocShare": {"on_trash": "frappe.flow.doctype.flow_session.flow_session.on_share_removed"},
}

# a session's tools run as its owner, so its content is theirs alone. An agent's or model's
# roles limit who may use it directly, and an agent's skills are read with it.
has_permission = {
	"Flow Session": "frappe.flow.permissions.has_session_permission",
	"Flow Run": "frappe.flow.permissions.has_session_permission",
	"Flow Agent Memory": "frappe.flow.permissions.has_memory_permission",
	"Flow Agent": "frappe.flow.permissions.has_role_permission",
	"Flow Model": "frappe.flow.permissions.has_role_permission",
	"Flow Skill": "frappe.flow.permissions.has_skill_permission",
}
permission_query_conditions = {
	"Flow Session": "frappe.flow.permissions.session_query_conditions",
	"Flow Run": "frappe.flow.permissions.session_query_conditions",
	"Flow Agent Memory": "frappe.flow.permissions.memory_query_conditions",
	"Flow Agent": "frappe.flow.permissions.role_query_conditions",
	"Flow Model": "frappe.flow.permissions.role_query_conditions",
	"Flow Skill": "frappe.flow.permissions.skill_query_conditions",
}

# Flow's references to other docs are bookkeeping — they must never block deleting
# the referenced doc. A knowledge chunk indexes a doc; a Flow Run records the doc a
# trigger acted on. The incremental sweep removes orphaned chunks afterwards.
# A session's Flow Model reference is historical bookkeeping and must not block deletion.
ignore_links_on_delete = ["Flow Knowledge Chunk", "Flow Run", "Flow Session"]

default_log_clearing_doctypes = {
	"Flow Session": 90,
}

scheduler_events = {
	"daily": [
		"frappe.flow.knowledge.ingest.sync_due_sources",
	],
	"cron": {
		"*/5 * * * *": [
			"frappe.flow.triggers.dispatch_scheduled",
			"frappe.flow.daemon.lifecycle.keep_alive",
		],
	},
}

after_install = [
	"frappe.flow.permissions.ensure_flow_role",
	"frappe.flow.assistant.sync_builtin_assistant",
	"frappe.flow.daemon.lifecycle.after_install",
]
after_migrate = [
	"frappe.flow.permissions.ensure_flow_role",
	"frappe.flow.assistant.sync_builtin_assistant",
	"frappe.flow.lib.agent.sync_agents",
	"frappe.flow.lib.agent.sync_tools",
	"frappe.flow.daemon.lifecycle.after_migrate",
]
after_app_install = [
	"frappe.flow.assistant.sync_assistant_skills",
	"frappe.flow.lib.agent.sync_agents",
	"frappe.flow.lib.agent.sync_tools",
]
after_app_uninstall = ["frappe.flow.assistant.sync_assistant_skills"]
before_uninstall = ["frappe.flow.daemon.lifecycle.remove_site"]

extend_bootinfo = "frappe.flow.boot.boot_session"
