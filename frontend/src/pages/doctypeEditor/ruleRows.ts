// The rule rows of the field and container panels: the condition each edits, its sentence, and
// what it says with none. English here; the panels translate each string where they show it.
import type { LayoutTreeColumn, LayoutTreeSection, LayoutTreeTab } from "./layoutTree";

export interface RuleRow {
	/** The field property, or the layout tree key on a container. */
	key: string;
	label: string;
	/** The full sentence, `{0}` being the rule in words. */
	sentence: string;
	empty: string;
	/** Under the empty builder. */
	note: string;
}

export const FIELD_RULES: RuleRow[] = [
	{
		key: "depends_on",
		label: "Visible if",
		sentence: "Visible if {0}",
		empty: "Always",
		note: "Always visible. Add a condition to show it only sometimes.",
	},
	{
		key: "mandatory_depends_on",
		label: "Mandatory if",
		sentence: "Mandatory if {0}",
		empty: "Never",
		note: "Never required by a condition. Add one to require it sometimes.",
	},
	{
		key: "read_only_depends_on",
		label: "Read-only if",
		sentence: "Read-only if {0}",
		empty: "Never",
		note: "Always editable. Add a condition to lock it sometimes.",
	},
];

const VISIBLE = { key: "dependsOn", label: "Visible if", sentence: "Visible if {0}", empty: "Always" };

export const CONTAINER_RULES: Record<"tab" | "section" | "column", RuleRow[]> = {
	tab: [{ ...VISIBLE, note: "Always visible. Add a condition to show the tab only sometimes." }],
	section: [
		{ ...VISIBLE, note: "Always visible. Add a condition to show the section only sometimes." },
		{
			key: "collapsibleDependsOn",
			label: "Starts open if",
			sentence: "Starts open if {0}",
			empty: "Never",
			note: "Starts closed. Add a condition to open it when it matters.",
		},
	],
	column: [{ ...VISIBLE, note: "Always visible. Add a condition to show the column only sometimes." }],
};

// "Opens expanded" holds until a rule is set: the rule then decides, so the switch hides.
const STARTS_OPEN = {
	empty: "Always",
	note: "Starts open. Add a condition to open it only when it matters.",
};

type Container = LayoutTreeTab | LayoutTreeSection | LayoutTreeColumn;

/** A container's rule rows; "Starts open if" only on a collapsible section, "Always" when it opens expanded. */
export function containerRules(kind: keyof typeof CONTAINER_RULES, node: Container): RuleRow[] {
	const section = kind === "section" ? (node as LayoutTreeSection) : null;
	return CONTAINER_RULES[kind]
		.filter((rule) => rule.key !== "collapsibleDependsOn" || section?.collapsible)
		.map((rule) => (rule.key === "collapsibleDependsOn" && section?.opened ? { ...rule, ...STARTS_OPEN } : rule));
}

/** The value a rule row edits, on a field or a container. */
export function ruleValue(node: object, rule: RuleRow): string {
	return String((node as Record<string, unknown>)[rule.key] ?? "");
}
