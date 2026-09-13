// How Flow's tools read in the transcript and approval cards: a present-tense label,
// an icon and the one-line subject of the call. Unknown (custom) tools fall back to
// the core's humanized name.
const LABELS = {
	find_doctypes: "Finding DocTypes",
	describe: "Reading DocType Meta",
	read: "Reading Records",
	create: "Creating Records",
	update: "Updating Records",
	delete: "Deleting Records",
	run_action: "Running Document Actions",
	execute: "Running Code",
	search_knowledge: "Searching Knowledge",
	search_attachments: "Searching Attachments",
	update_memory: "Saving Memory",
	load_skill: "Loading Skill",
};

const ICONS = {
	find_doctypes: "search",
	describe: "layers",
	read: "database",
	create: "file-plus",
	update: "edit-3",
	delete: "trash-2",
	run_action: "play",
	execute: "code",
	search_knowledge: "book-open",
	search_attachments: "paperclip",
	update_memory: "bookmark",
	load_skill: "book",
};

const SUBJECT_KEYS = ["doctype", "query", "search", "name", "action", "description", "content"];

export function presentTool(name, args = {}) {
	const label = LABELS[name];
	if (!label) return {};
	return { icon: ICONS[name], label, subject: subject(args) };
}

function subject(args) {
	for (const key of SUBJECT_KEYS) {
		const value = args?.[key];
		if (typeof value === "string" && value.trim())
			return value.length > 80 ? value.slice(0, 77) + "…" : value;
	}
	return "";
}
