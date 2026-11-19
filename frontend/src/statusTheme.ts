// The Badge theme for a status or workflow state value, from meta alone (desk v1's indicator order).
export type StatusTheme = "gray" | "blue" | "green" | "orange" | "red";

export interface StatusMeta {
	fields?: { fieldname: string; fieldtype?: string }[];
	states?: { title?: string; color?: string }[];
	workflow_state_field?: string | null;
	workflow_state_styles?: Record<string, string>;
}

const STYLE_THEMES: Record<string, StatusTheme> = {
	Success: "green",
	Warning: "orange",
	Danger: "red",
	Primary: "blue",
	Info: "blue",
};

const STATE_COLOR_THEMES: Record<string, StatusTheme> = {
	Blue: "blue",
	Cyan: "blue",
	"Light Blue": "blue",
	Purple: "blue",
	Gray: "gray",
	Green: "green",
	Orange: "orange",
	Yellow: "orange",
	Red: "red",
	Pink: "red",
};

// Desk v1's `guess_style`: the first group with a word inside the value wins.
const WORD_THEMES: [StatusTheme, string[]][] = [
	["orange", ["Pending", "Review", "Medium", "Not Approved"]],
	["red", ["Open", "Urgent", "High", "Failed", "Rejected", "Error"]],
	[
		"green",
		[
			"Closed",
			"Finished",
			"Converted",
			"Completed",
			"Complete",
			"Confirmed",
			"Approved",
			"Yes",
			"Active",
			"Available",
			"Paid",
			"Success",
		],
	],
	["blue", ["Submitted"]],
];

/** The theme of a workflow state: its Workflow State's style, else gray. */
export function workflowTheme(meta: StatusMeta | null | undefined, state: string): StatusTheme {
	return STYLE_THEMES[meta?.workflow_state_styles?.[state] ?? ""] ?? "gray";
}

/** The theme of a list cell, or null when the column is not the workflow state or `status` field. */
export function listStatusTheme(
	meta: StatusMeta | null | undefined,
	fieldname: string,
	value: unknown,
): StatusTheme | null {
	if (value == null || value === "") return null;
	const text = String(value);
	if (fieldname === meta?.workflow_state_field) return workflowTheme(meta, text);
	if (fieldname !== "status" || !isPlainStatus(meta, fieldname)) return null;
	const color = meta?.states?.find((state) => state.title === text)?.color;
	return (color && STATE_COLOR_THEMES[color]) || guessTheme(text);
}

function guessTheme(text: string): StatusTheme {
	return WORD_THEMES.find(([, words]) => words.some((word) => text.includes(word)))?.[0] ?? "gray";
}

// A Link status (CRM's) keeps its own mark and title, and a long-text one is no badge.
function isPlainStatus(meta: StatusMeta | null | undefined, fieldname: string): boolean {
	const field = meta?.fields?.find((one) => one.fieldname === fieldname);
	return field?.fieldtype === "Select" || field?.fieldtype === "Data";
}
