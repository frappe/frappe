app_name = "flow"
app_title = "Flow"
app_publisher = "Shrihari Mahabal"
app_description = "Frappe Flow — native AI agents, tools, and triggers for Frappe"
app_email = "shriharimahabal08@gmail.com"
app_license = "mit"

export_python_type_annotations = True

app_include_js = ["ai.bundle.js"]

doc_events = {
	"*": {
		"after_insert": "flow.triggers.dispatch",
		"on_update": "flow.triggers.dispatch",
		"on_submit": "flow.triggers.dispatch",
		"on_cancel": "flow.triggers.dispatch",
		"on_trash": "flow.triggers.dispatch",
	}
}

scheduler_events = {
	"cron": {
		"* * * * *": [
			"flow.triggers.dispatch_scheduled",
		],
	},
}

after_migrate = ["flow.assistant.sync_builtin_assistant"]
