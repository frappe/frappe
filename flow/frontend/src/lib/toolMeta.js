// Tool name/args → plain-English label + readable (never JSON) argument rendering.
import { __ } from "@/lib/translate";

export function parseArgs(args) {
	if (!args) return {};
	if (typeof args === "object") return args;
	try {
		return JSON.parse(args);
	} catch {
		return {};
	}
}

// snake_case / a name → "Snake case".
export function humanize(name) {
	return String(name || "")
		.replace(/_/g, " ")
		.replace(/^./, (c) => c.toUpperCase());
}

// Present-tense label per builtin; custom tools fall back to a humanized name.
const LABELS = {
	find_doctypes: "Finding relevant DocTypes",
	describe: "Reading DocType Meta",
	read: "Reading Doctype Records",
	search_knowledge: "Searching Knowledge",
	execute: "Executing",
	create: "Creating Records",
	update: "Updating Records",
	delete: "Deleting Records",
	run_action: "Running Document Actions",
};

export function toolLabel(name) {
	return LABELS[name] ? __(LABELS[name]) : humanize(name);
}

const isPlainObject = (v) => v !== null && typeof v === "object" && !Array.isArray(v);

function scalar(v) {
	if (v === null || v === undefined) return "—";
	if (typeof v === "boolean") return v ? __("Yes") : __("No");
	return String(v);
}

// Value → indented plain text (YAML-ish), no braces or quotes.
export function readableLines(value, indent = 0) {
	const pad = "  ".repeat(indent);
	const out = [];
	if (Array.isArray(value)) {
		if (!value.length) return [`${pad}${__("(none)")}`];
		for (const v of value) {
			if (isPlainObject(v) || Array.isArray(v)) {
				out.push(`${pad}-`);
				out.push(...readableLines(v, indent + 1));
			} else {
				out.push(`${pad}- ${scalar(v)}`);
			}
		}
	} else if (isPlainObject(value)) {
		for (const [k, v] of Object.entries(value)) {
			if (isPlainObject(v) || Array.isArray(v)) {
				out.push(`${pad}${humanize(k)}:`);
				out.push(...readableLines(v, indent + 1));
			} else {
				out.push(`${pad}${humanize(k)}: ${scalar(v)}`);
			}
		}
	} else {
		out.push(`${pad}${scalar(value)}`);
	}
	return out;
}

const isScalar = (v) => v === null || typeof v !== "object";

// One entry per top-level arg → { key, label, kind, value }. "inline" = scalar or
// scalar list (on the key's row); "block" = long string / nested (own block).
export function argEntries(args) {
	const obj = parseArgs(args);
	return Object.entries(obj).map(([key, value]) => {
		const label = humanize(key);
		if (isScalar(value)) {
			const long = typeof value === "string" && (value.includes("\n") || value.length > 80);
			return {
				key,
				label,
				kind: long ? "block" : "inline",
				value: long ? value : scalar(value),
			};
		}
		if (Array.isArray(value) && value.every(isScalar)) {
			return {
				key,
				label,
				kind: "inline",
				value: value.map(scalar).join(", ") || __("(none)"),
			};
		}
		return { key, label, kind: "block", value: readableLines(value).join("\n") };
	});
}
