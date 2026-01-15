EMAILS = ["test_user@example.com", "test_user1@example.com", "test_user2@example.com"]
BASE_AUTOMATION_RULE = {
	"presets": [["status", "equals", "Open"]],
	"rule": [
		{
			"type": "if",
			"conditions": [["priority", "equals", "Medium"]],
			"actions": [{"type": "set", "field": "allocated_to", "value": EMAILS[0]}],
		},
		{
			"type": "if",
			"conditions": [["priority", "equals", "High"]],
			"actions": [{"type": "set", "field": "allocated_to", "value": EMAILS[1]}],
		},
		{
			"type": "else",
			"condition": "True",
			"actions": [{"type": "set", "field": "allocated_to", "value": EMAILS[2]}],
		},
	],
}

BASE_EMAIL_AUTOMATION_RULE = {
	"presets": [["status", "equals", "Open"]],
	"rule": [
		{
			"type": "if",
			"conditions": [["priority", "equals", "High"]],
			"actions": [{"field": "allocated_to", "type": "set", "value": EMAILS[0]}],
		},
		{
			"create_communication": False,
			"doctype": "Email Template",
			"message": "",
			"template": "Test Template",
			"to": "allocated_to",
			"type": "email",
			"via": "template",
		},
		{
			"create_communication": True,
			"doctype": "Email Template",
			"message": "<p>Blah Blah {{status}}</p>",
			"subject": "Blah blah blah",
			"template": "",
			"to": "allocated_to",
			"type": "email",
			"via": "rich_text",
		},
	],
}

DAYS_OFFSET_AUTOMATION_RULE = {
	"presets": [],
	"rule": [
		{
			"type": "email",
			"to": "allocated_to",
			"via": "template",
			"template": "Hello",
			"message": "",
			"doctype": "Email Template",
			"create_communication": True,
		}
	],
}
