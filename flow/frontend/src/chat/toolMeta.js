import { __ } from "@flow/ui-core/translate.js";

import ApiView from "./tools/ApiView.vue";
import ArgsView from "./tools/ArgsView.vue";
import CodeCard from "./tools/CodeCard.vue";
import CodeView from "./tools/CodeView.vue";
import CreateView from "./tools/CreateView.vue";
import FunctionCard from "./tools/FunctionCard.vue";
import NamesView from "./tools/NamesView.vue";
import ReadView from "./tools/ReadView.vue";
import ReportView from "./tools/ReportView.vue";
import { blank, humanize, parseResult } from "./tools/result.js";
import ResultView from "./tools/ResultView.vue";
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
		label: __("Finding DocTypes"),
		done: __("Found DocTypes"),
	},
	describe: {
		icon: "lucide-layers",
		label: __("Reading DocType meta"),
		done: __("Read DocType meta"),
	},
	find_apis: {
		icon: "lucide-search-code",
		label: __("Finding APIs"),
		done: __("Found APIs"),
	},
	describe_api: {
		icon: "lucide-square-function",
		label: __("Reading an API"),
		done: __("Read APIs"),
		// a document's own method by its title; a function by its path, as code
		subject: (args) =>
			args.doctype ? `${args.doctype}: ${functionTitle(args.method ?? "")}` : args.method ?? "",
	},
	call_api: {
		icon: "lucide-play",
		label: __("Calling API"),
		done: __("Called APIs"),
		view: ApiView,
		argsView: FunctionCard,
		asks: true,
		subject: (args) => args.method ?? "",
	},
	read_records: {
		icon: "lucide-database",
		label: __("Reading records"),
		done: __("Read records"),
		view: ReadView,
		stat: (result) => recordsOf(result.records.length, result.total),
	},
	run_report: {
		icon: "lucide-chart-column",
		label: __("Running report"),
		done: __("Ran reports"),
		view: ReportView,
		stat: (result) => rowsOf(result.rows.length, result.row_count),
	},
	create: {
		icon: "lucide-file-plus",
		label: __("Creating records"),
		done: __("Created records"),
		view: CreateView,
		asks: true,
		stat: (result) => __("{0} created", [tally(result.created)]),
	},
	update: {
		icon: "lucide-pen-line",
		label: __("Updating records"),
		done: __("Updated records"),
		view: NamesView,
		asks: true,
		stat: (result) => __("{0} updated", [tally(result.updated)]),
	},
	delete: {
		icon: "lucide-trash-2",
		label: __("Deleting records"),
		done: __("Deleted records"),
		view: NamesView,
		asks: true,
		stat: (result) => __("{0} deleted", [tally(result.deleted)]),
	},
	run_action: {
		icon: "lucide-play",
		label: (args) =>
			ACTIONS[args.action] ?? (isFunction(args) ? __("Calling API") : actionName(args.action)),
		done: (args) => (isFunction(args) ? __("Called APIs") : __("Ran document actions")),
		view: (args) => (isFunction(args) ? ApiView : NamesView),
		argsView: (args) => (isFunction(args) ? FunctionCard : NamesView),
		asks: true,
		stat: (result) =>
			result.action === "rename"
				? __("renamed")
				: result.results
				? __("{0} done", [tally(result.results)])
				: "",
		// a function by its dotted path, as the model called it
		subject: (args) => (isFunction(args) ? args.action : null),
	},
	execute: {
		icon: "lucide-code",
		label: __("Running code"),
		done: __("Ran code"),
		view: CodeView,
		argsView: CodeCard,
		asks: true,
	},
	// its card is a password box that answers the card itself
	request_secret: {
		icon: "lucide-key-round",
		label: __("Saving a password"),
		done: __("Saved a password"),
		argsView: SecretView,
		asks: true,
		ownAnswers: true,
	},
	search_knowledge: {
		icon: "lucide-book-open",
		label: __("Searching knowledge"),
		done: __("Searched knowledge"),
		view: SnippetView,
		stat: (result) => hits(result.length),
	},
	search_attachments: {
		icon: "lucide-paperclip",
		label: __("Searching attachments"),
		done: __("Searched attachments"),
		view: SnippetView,
		stat: (result) => hits(result.length),
	},
	search_docs: {
		icon: "lucide-book-open",
		label: __("Searching the docs"),
		done: __("Searched the docs"),
	},
	update_memory: {
		icon: "lucide-bookmark",
		label: __("Saving memory"),
		done: __("Saved memory"),
	},
	load_skill: { icon: "lucide-book", label: __("Loading skill"), done: __("Loaded skills") },
	read_screen: {
		icon: "lucide-monitor",
		label: __("Reading screen"),
		done: __("Read the screen"),
		// the page it read, by its title
		subject: (args, result) => parseResult(result)?.title,
	},
	// the flow server's own tool: its row opens the child's thread in the workspace panel
	subagent: { icon: "lucide-bot", label: __("Sub-agent"), done: __("Ran sub-agents") },
};

const ACTIONS = {
	submit: __("Submitting"),
	cancel: __("Cancelling"),
	amend: __("Amending"),
	rename: __("Renaming"),
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
	if (!tool) return { ...customCard(args), resultComponent: ResultView };
	const view = pick(tool.view, args);
	const parsed = tool.stat ? parseResult(result) : null;
	const stat = parsed ? readStat(tool, parsed) : "";
	// a cut result is no longer JSON, and an older one may not fit the view, so the
	// view of any return draws them; execute's view already does
	const plain = (result?.details?.truncation?.truncated || stat === null) && view !== CodeView;
	return {
		icon: tool.icon,
		label: typeof tool.label === "function" ? tool.label(args) : tool.label,
		done: typeof tool.done === "function" ? tool.done(args) : tool.done,
		subject: tool.subject?.(args, result) ?? subject(args),
		codeSubject: isCodeSubject(name, args),
		stat: stat ?? "",
		expandable: view ? undefined : false,
		argsComponent: tool.asks ? pick(tool.argsView, args) ?? view : undefined,
		ownAnswers: tool.ownAnswers,
		resultComponent: plain ? ResultView : view,
	};
}

// a workflow step or a document's own method by its name: "Make payment"
function actionName(action = "") {
	const words = action.replace(/_/g, " ");
	return words ? words[0].toUpperCase() + words.slice(1) : __("Running document actions");
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

// a custom tool's card shows its arguments in words, or nothing when it has none
function customCard(args) {
	return blank(args) ? { body: "" } : { argsComponent: ArgsView };
}

// a view may depend on the call: run_action runs a record's action, or a function
function pick(view, args) {
	return typeof view === "function" ? view(args) : view;
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

function hits(n) {
	return n === 1 ? __("1 hit") : __("{0} hits", [n]);
}

function recordsOf(shown, total) {
	if (shown < total)
		return total === 1 ? __("{0} of 1 record", [shown]) : __("{0} of {1} records", [shown, total]);
	return total === 1 ? __("1 record") : __("{0} records", [total]);
}

function rowsOf(shown, total) {
	if (shown < total)
		return total === 1 ? __("{0} of 1 row", [shown]) : __("{0} of {1} rows", [shown, total]);
	return total === 1 ? __("1 row") : __("{0} rows", [total]);
}

function tally(done) {
	return done?.length ?? 0;
}
