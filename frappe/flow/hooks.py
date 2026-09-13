app_name = "flow"
app_title = "Flow"
app_publisher = "Shrihari Mahabal"
app_description = "Frappe Flow — native AI agents, tools, and triggers for Frappe"
app_email = "shriharimahabal08@gmail.com"
app_license = "agpl-3.0"

export_python_type_annotations = True

# The /flow page: a Vite app (frontend/) built by `yarn build` into public/frontend, its
# entry copied to www/flow/index.html. Every path under /flow serves that page.
add_to_apps_screen = [
	{
		"name": "flow",
		"logo": "/assets/flow/frontend/flow.png",
		"title": "Flow",
		"route": "/flow",
		"has_permission": "flow.permissions.has_app_permission",
	}
]
website_route_rules = [{"from_route": "/flow/<path:app_path>", "to_route": "flow"}]

doc_events = {
	"*": {
		"after_insert": "flow.triggers.dispatch",
		"on_update": "flow.triggers.dispatch",
		"on_submit": "flow.triggers.dispatch",
		"on_cancel": "flow.triggers.dispatch",
		"on_trash": "flow.triggers.dispatch",
	}
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
		"flow.knowledge.ingest.sync_due_sources",
	],
	"cron": {
		"*/5 * * * *": [
			"flow.triggers.dispatch_scheduled",
			"flow.daemon.lifecycle.keep_alive",
		],
	},
}

after_install = ["flow.permissions.ensure_flow_role", "flow.daemon.lifecycle.after_install"]
after_migrate = [
	"flow.permissions.ensure_flow_role",
	"flow.assistant.sync_builtin_assistant",
	"flow.lib.agent.sync_agents",
	"flow.daemon.lifecycle.after_migrate",
]
after_app_install = ["flow.lib.agent.sync_agents"]
before_uninstall = ["flow.daemon.lifecycle.remove_site"]

extend_bootinfo = "flow.boot.boot_session"
