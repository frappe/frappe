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
		// The copy starts disabled and opens unsaved, so it never runs before the person enables and saves it.
		run: (shell, name) =>
			shell.create("Automation Flow", { values: { __copy_of: name, enabled: 0 } }),
	},
];
