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

// How Flow's tools read in the transcript and approval cards: a present-tense label, a
// past-tense `done` for a finished run, an icon, the one-line subject of the call, the count
// it ended on, and the view that draws its records. `view` renders the result in the
// expanded row, and the arguments on the approval card of a tool that asks first. A tool
// without one is a lookup the agent did to orient itself: one row, no dropdown.
const TOOLS = {
	find_doctypes: {
		icon: "lucide-search",
		label: "Finding DocTypes",
		done: "Found DocTypes",
	},
	describe: {
		icon: "lucide-layers",
		label: "Reading DocType meta",
		done: "Read DocType meta",
	},
	find_apis: {
		icon: "lucide-search-code",
		label: "Finding APIs",
		done: "Found APIs",
	},
	describe_api: {
		icon: "lucide-square-function",
		label: "Reading an API",
		done: "Read APIs",
		// a document's own method by its title; a function by its path, as code
		subject: (args) =>
			args.doctype ? `${args.doctype}: ${functionTitle(args.method ?? "")}` : args.method ?? "",
	},
	call_api: {
		icon: "lucide-play",
		label: "Calling API",
		done: "Called APIs",
		view: JsonView,
		argsView: FunctionCard,
		asks: true,
		subject: (args) => args.method ?? "",
	},
	read_records: {
		icon: "lucide-database",
		label: "Reading records",
		done: "Read records",
		view: ReadView,
		stat: (result) => countOf(result.records.length, result.total, "record"),
	},
	run_report: {
		icon: "lucide-chart-column",
		label: "Running report",
		done: "Ran reports",
		view: ReportView,
		stat: (result) => countOf(result.rows.length, result.row_count, "row"),
	},
	create: {
		icon: "lucide-file-plus",
		label: "Creating records",
		done: "Created records",
		view: CreateView,
		asks: true,
		stat: (result) => outcome(result.created, "created"),
	},
	update: {
		icon: "lucide-pen-line",
		label: "Updating records",
		done: "Updated records",
		view: NamesView,
		asks: true,
		stat: (result) => outcome(result.updated, "updated"),
	},
	delete: {
		icon: "lucide-trash-2",
		label: "Deleting records",
		done: "Deleted records",
		view: NamesView,
		asks: true,
		stat: (result) => outcome(result.deleted, "deleted"),
	},
	run_action: {
		icon: "lucide-play",
		label: (args) =>
			ACTIONS[args.action] ?? (isFunction(args) ? "Calling API" : actionName(args.action)),
		done: (args) => (isFunction(args) ? "Called APIs" : "Ran document actions"),
		view: NamesView,
		argsView: (args) => (isFunction(args) ? FunctionCard : NamesView),
		asks: true,
		stat: (result) =>
			result.action === "rename"
				? "renamed"
				: result.results
				? outcome(result.results, "done")
				: "",
		// a function by its dotted path, as the model called it
		subject: (args) => (isFunction(args) ? args.action : null),
	},
	execute: {
		icon: "lucide-code",
		label: "Running code",
		done: "Ran code",
		view: CodeView,
		argsView: CodeCard,
		asks: true,
	},
	// its card is a password box that answers the card itself
	request_secret: {
		icon: "lucide-key-round",
		label: "Saving a password",
		done: "Saved a password",
		argsView: SecretView,
		asks: true,
		ownAnswers: true,
	},
	search_knowledge: {
		icon: "lucide-book-open",
		label: "Searching knowledge",
		done: "Searched knowledge",
		view: SnippetView,
		stat: (result) => count(result.length, "hit"),
	},
	search_attachments: {
		icon: "lucide-paperclip",
		label: "Searching attachments",
		done: "Searched attachments",
		view: SnippetView,
		stat: (result) => count(result.length, "hit"),
	},
	update_memory: {
		icon: "lucide-bookmark",
		label: "Saving memory",
		done: "Saved memory",
	},
	load_skill: { icon: "lucide-book", label: "Loading skill", done: "Loaded skills" },
	read_screen: {
		icon: "lucide-monitor",
		label: "Reading screen",
		done: "Read the screen",
		// the page it read, by its title
		subject: (args, result) => parseResult(result)?.title,
	},
	// the flow server's own tool: its row opens the child's thread in the workspace panel
	subagent: { icon: "lucide-bot", label: "Sub-agent", done: "Ran sub-agents" },
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
		done: typeof tool.done === "function" ? tool.done(args) : tool.done,
		subject: tool.subject?.(args, result) ?? subject(args),
		codeSubject: isCodeSubject(name, args),
		stat: stat ?? "",
		expandable: tool.view ? undefined : false,
		argsComponent: tool.asks ? argsView(tool, args) : undefined,
		ownAnswers: tool.ownAnswers,
		resultComponent: plain ? JsonView : tool.view,
	};
}

// a workflow step or a document's own method by its name: "Make payment"
function actionName(action = "") {
	const words = action.replace(/_/g, " ");
	return words ? words[0].toUpperCase() + words.slice(1) : "Running document actions";
}

// a function's dotted path reads as code
function isCodeSubject(name, args) {
	if (name === "run_action") return isFunction(args);
	return name === "call_api" || (name === "describe_api" && !args.doctype);
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
