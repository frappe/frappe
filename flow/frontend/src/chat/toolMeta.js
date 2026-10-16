import CodeView from "./tools/CodeView.vue";
import CreateView from "./tools/CreateView.vue";
import JsonView from "./tools/JsonView.vue";
import NamesView from "./tools/NamesView.vue";
import ReadView from "./tools/ReadView.vue";
import ReportView from "./tools/ReportView.vue";
import { parseResult } from "./tools/result.js";
import SnippetView from "./tools/SnippetView.vue";

// How Flow's tools read in the transcript and approval cards: a present-tense label, an
// icon, the one-line subject of the call, the count it ended on, and the view that draws
// its records. `view` renders the result in the expanded row, and the arguments on the
// approval card of a tool that asks first. A tool without one is a lookup the agent did
// to orient itself: one row, no dropdown.
const TOOLS = {
	find_doctypes: {
		icon: "search",
		label: "Finding DocTypes",
		stat: (result) => countOf(result.doctypes.length, result.total, "match", "matches"),
	},
	describe: {
		icon: "layers",
		label: "Reading DocType Meta",
		stat: (result) => count(result.fields?.length ?? 0, "field"),
	},
	read_records: {
		icon: "database",
		label: "Reading Records",
		view: ReadView,
		stat: (result) => countOf(result.records.length, result.total, "record"),
	},
	run_report: {
		icon: "bar-chart-2",
		label: "Running Report",
		view: ReportView,
		stat: (result) => countOf(result.rows.length, result.row_count, "row"),
	},
	create: {
		icon: "file-plus",
		label: "Creating Records",
		view: CreateView,
		asks: true,
		stat: (result) => outcome(result.created, "created"),
	},
	update: {
		icon: "edit-3",
		label: "Updating Records",
		view: NamesView,
		asks: true,
		stat: (result) => outcome(result.updated, "updated"),
	},
	delete: {
		icon: "trash-2",
		label: "Deleting Records",
		view: NamesView,
		asks: true,
		stat: (result) => outcome(result.deleted, "deleted"),
	},
	run_action: {
		icon: "play",
		label: (args) => ACTIONS[args.action] ?? "Running Document Actions",
		view: NamesView,
		asks: true,
		stat: (result) =>
			result.action === "rename" ? "renamed" : outcome(result.results, "done"),
	},
	execute: { icon: "code", label: "Running Code", view: CodeView, asks: true },
	search_knowledge: {
		icon: "book-open",
		label: "Searching Knowledge",
		view: SnippetView,
		stat: (result) => count(result.length, "hit"),
	},
	search_attachments: {
		icon: "paperclip",
		label: "Searching Attachments",
		view: SnippetView,
		stat: (result) => count(result.length, "hit"),
	},
	update_memory: {
		icon: "bookmark",
		label: "Saving Memory",
		stat: (result) => result.action ?? "",
	},
	load_skill: { icon: "book", label: "Loading Skill" },
	// the flow server's own tool: its row opens the child's thread in the workspace panel
	subagent: { icon: "bot", label: "Sub-agent" },
};

const ACTIONS = {
	submit: "Submitting",
	cancel: "Cancelling",
	amend: "Amending",
	rename: "Renaming",
};

const SUBJECT_KEYS = [
	"doctype",
	"report_name",
	"query",
	"search",
	"name",
	"action",
	"description",
	"content",
];

// the flow server's file tools keep the core's own rows, which fold a read's file text
const FILE_TOOLS = new Set(["read", "grep"]);

export function presentTool(name, args = {}, result = null) {
	if (FILE_TOOLS.has(name)) return {};
	const tool = TOOLS[name];
	// a custom Imported or Script tool: its return is the point, so always show it
	if (!tool) return { resultComponent: JsonView };
	const parsed = tool.stat ? parseResult(result) : null;
	const stat = parsed ? readStat(tool, parsed) : "";
	// a cut result is no longer JSON, and an older one may not fit the view, so show
	// their text; execute's view already does
	const plain =
		(result?.details?.truncation?.truncated || stat === null) && tool.view !== CodeView;
	return {
		icon: tool.icon,
		label: typeof tool.label === "function" ? tool.label(args) : tool.label,
		subject: subject(args),
		stat: stat ?? "",
		expandable: tool.view ? undefined : false,
		argsComponent: tool.asks ? tool.view : undefined,
		resultComponent: plain ? JsonView : tool.view,
	};
}

// null for a result saved before its tool's return changed
function readStat(tool, parsed) {
	try {
		return tool.stat(parsed);
	} catch {
		return null;
	}
}

function subject(args) {
	for (const key of SUBJECT_KEYS) {
		const value = args?.[key];
		if (typeof value === "string" && value.trim()) {
			const line = value.split("\n")[0];
			return line.length > 80 ? line.slice(0, 77) + "…" : line;
		}
	}
	return "";
}

function count(n, singular, plural = `${singular}s`) {
	return `${n} ${n === 1 ? singular : plural}`;
}

function countOf(shown, total, singular, plural) {
	const all = count(total, singular, plural);
	return shown < total ? `${shown} of ${all}` : all;
}

function outcome(done, verb) {
	return `${done?.length ?? 0} ${verb}`;
}
