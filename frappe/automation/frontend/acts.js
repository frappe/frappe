// Frappe's global acts on desk v2's shell surface, run as `shell.frappe.<name>`.
import { __ } from "frappe/i18n";

export default [
	{
		name: "duplicate_automation_flow",
		get label() {
			return __("Duplicate");
		},
		icon: "lucide-copy",
		right: { doctype: "Automation Flow", ptype: "create" },
		description:
			"Open the Create dialog with a copy of an Automation Flow, disabled. The person names and saves the copy. Data is the created flow, or null when the person closed the dialog.",
		input: { type: "string", minLength: 1, description: "The name of the flow to copy." },
		asks: ["dialog"],
		run: (shell, name) =>
			shell.create("Automation Flow", { values: { __copy_of: name, enabled: 0 } }),
	},
];
