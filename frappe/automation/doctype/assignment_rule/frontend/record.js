// Assignment Rule's record page: the target doctype's fields as choices, the rule's hint and the day presets.
import { getMeta } from "@framework/ui/api";
import { __ } from "frappe/i18n";

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
const WEEKENDS = ["Saturday", "Sunday"];
const PRESETS = "assignment_day_presets";

export default {
	onRefresh(page) {
		page.fields.update("document_type", { link_filters: { name: ["!=", "ToDo"] } });
		describeRule(page);
		offerTargetFields(page);
		addDayPresets(page);
	},
	document_type: (page) => page.refresh(),
	rule: (page) => page.refresh(),
};

function describeRule(page) {
	const description = ruleDescriptions()[page.doc.rule];
	if (description) page.fields.update("rule", { description });
}

function offerTargetFields(page) {
	const doctype = page.doc.document_type;
	if (!doctype) return;
	const fields = page.cached(
		`fields:${doctype}`,
		async () => (await getMeta(doctype)).data?.fields ?? []
	);
	if (!fields) return;
	page.fields.update("field", { options: choices(["owner"], fields.filter(namesAUser)) });
	const dates = fields.filter((df) => ["Date", "Datetime"].includes(df.fieldtype));
	page.fields.update(
		"due_date_based_on",
		dates.length ? { options: choices([""], dates) } : { hidden: true }
	);
}

function addDayPresets(page) {
	page.header.add(
		{ name: PRESETS, label: __("Set days"), display: "dropdown" },
		{ before: "save" }
	);
	for (const preset of dayPresets())
		page.header.add({
			name: `${PRESETS}_${preset.name}`,
			label: preset.label,
			group: PRESETS,
			// A new record has no record rights before its insert, which checks create.
			right: page.isNew ? undefined : "write",
			run: (page) => {
				page.doc.assignment_days = preset.days.map((day) => ({ day }));
			},
		});
}

function ruleDescriptions() {
	return {
		"Round Robin": __("Assign one by one, in sequence"),
		"Load Balancing": __("Assign to the one who has the least assignments"),
		"Based on Field": __("Assign to the user set in this field"),
	};
}

function dayPresets() {
	return [
		{ name: "weekdays", label: __("Weekdays"), days: WEEKDAYS },
		{ name: "weekends", label: __("Weekends"), days: WEEKENDS },
		{ name: "all_days", label: __("All Days"), days: [...WEEKDAYS, ...WEEKENDS] },
	];
}

function namesAUser(df) {
	return (
		["Dynamic Link", "Data"].includes(df.fieldtype) ||
		(df.fieldtype === "Link" && df.options === "User")
	);
}

function choices(first, fields) {
	return [...first, ...fields.map((df) => df.fieldname)].join("\n");
}
