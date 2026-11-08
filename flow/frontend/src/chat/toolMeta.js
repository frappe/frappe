import CodeCard from "./tools/CodeCard.vue";
import CodeView from "./tools/CodeView.vue";
import CreateView from "./tools/CreateView.vue";
import FunctionCard from "./tools/FunctionCard.vue";
import JsonView from "./tools/JsonView.vue";
import NamesView from "./tools/NamesView.vue";
import ReadView from "./tools/ReadView.vue";
import ReportView from "./tools/ReportView.vue";
import { humanize, parseResult } from "./tools/result.js";
import SecretView from "./tools/SecretView.vue";
import SnippetView from "./tools/SnippetView.vue";

// How Flow's tools read in the transcript and approval cards: a present-tense label, an
// icon, the one-line subject of the call, the count it ended on, and the view that draws
// its records. `view` renders the result in the expanded row, and the arguments on the
// approval card of a tool that asks first. A tool without one is a lookup the agent did
// to orient itself: one row, no dropdown.
const TOOLS = {
	find_doctypes: {
		icon: "lucide-search",
		label: "Finding DocTypes",
		stat: (result) => countOf(result.doctypes.length, result.total, "match", "matches"),
	},
	describe: {
		icon: "lucide-layers",
		label: "Reading DocType Meta",
		stat: (result) => count(result.fields?.length ?? 0, "field"),
	},
	find_apis: {
		icon: "lucide-search-code",
		label: "Finding APIs",
		stat: (result) => count(result.length, "match", "matches"),
	},
	describe_api: {
		icon: "lucide-square-function",
		label: "Reading an API",
		stat: (result) => count(result.params?.length ?? 0, "argument"),
		subject: (args) =>
			[args.doctype, functionTitle(args.method ?? "")].filter(Boolean).join(": "),
	},
	call_api: {
		icon: "lucide-play",
		label: "Running a Function",
		view: JsonView,
		argsView: FunctionCard,
		asks: true,
		subject: (args, result) =>
			parseResult(result)?.title ?? functionTitle(args.method ?? ""),
	},
	read_records: {
		icon: "lucide-database",
		label: "Reading Records",
		view: ReadView,
		stat: (result) => countOf(result.records.length, result.total, "record"),
	},
	run_report: {
		icon: "lucide-chart-column",
		label: "Running Report",
		view: ReportView,
		stat: (result) => countOf(result.rows.length, result.row_count, "row"),
	},
	create: {
		icon: "lucide-file-plus",
		label: "Creating Records",
		view: CreateView,
		asks: true,
		stat: (result) => outcome(result.created, "created"),
	},
	update: {
		icon: "lucide-pen-line",
		label: "Updating Records",
		view: NamesView,
		asks: true,
		stat: (result) => outcome(result.updated, "updated"),
	},
	delete: {
		icon: "lucide-trash-2",
		label: "Deleting Records",
		view: NamesView,
		asks: true,
		stat: (result) => outcome(result.deleted, "deleted"),
	},
	run_action: {
		icon: "lucide-play",
		label: (args) =>
			ACTIONS[args.action] ??
			(isFunction(args) ? "Running a Function" : "Running Document Actions"),
		view: NamesView,
		argsView: (args) => (isFunction(args) ? FunctionCard : NamesView),
		asks: true,
		stat: (result) =>
			result.action === "rename"
				? "renamed"
				: result.results
				? outcome(result.results, "done")
				: "",
		// a function's dotted path is code: its result names it in words
		subject: (args, result) =>
			isFunction(args) ? parseResult(result)?.title ?? functionTitle(args.action) : null,
	},
	execute: {
		icon: "lucide-code",
		label: "Running Code",
		view: CodeView,
		argsView: CodeCard,
		asks: true,
	},
	// its card is a password box that answers the card itself
	request_secret: {
		icon: "lucide-key-round",
		label: "Saving a Password",
		argsView: SecretView,
		asks: true,
		ownAnswers: true,
	},
	search_knowledge: {
		icon: "lucide-book-open",
		label: "Searching Knowledge",
		view: SnippetView,
		stat: (result) => count(result.length, "hit"),
	},
	search_attachments: {
		icon: "lucide-paperclip",
		label: "Searching Attachments",
		view: SnippetView,
		stat: (result) => count(result.length, "hit"),
	},
	update_memory: {
		icon: "lucide-bookmark",
		label: "Saving Memory",
		stat: (result) => result.action ?? "",
	},
	load_skill: { icon: "lucide-book", label: "Loading Skill" },
	read_screen: {
		icon: "lucide-monitor",
		label: "Reading Screen",
		stat: (result) => result.title ?? "",
	},
	// the flow server's own tool: its row opens the child's thread in the workspace panel
	subagent: { icon: "lucide-bot", label: "Sub-agent" },
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

// the flow server's own tools keep the core's rows, which fold a read's file text
const CORE_TOOLS = new Set(["read", "grep", "web_fetch", "web_search"]);

export function presentTool(name, args = {}, result = null) {
	if (CORE_TOOLS.has(name)) return {};
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
		subject: tool.subject?.(args, result) ?? subject(args),
		stat: stat ?? "",
		expandable: tool.view ? undefined : false,
		argsComponent: tool.asks ? argsView(tool, args) : undefined,
		ownAnswers: tool.ownAnswers,
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

// a whitelisted function is named by its dotted path, as the server reads it (is_function_path)
function isFunction(args) {
	return typeof args?.action === "string" && /^\w+(\.\w+)+$/.test(args.action);
}

function argsView(tool, args) {
	return typeof tool.argsView === "function" ? tool.argsView(args) : tool.argsView ?? tool.view;
}

// as the server names it (function_title): the last two parts of its path, in words
function functionTitle(path) {
	return path.split(".").slice(-2).map(humanize).join(": ");
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
