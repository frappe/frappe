import { __ } from "frappe/i18n";
/**
 * Filter rows <-> the Python expression stored as `step_condition` (run by `safe_eval`: no builtins).
 * An expression that does not parse back is still valid; the editor falls back to text.
 */

const NUMERIC_FIELDTYPES = ["Int", "Float", "Currency", "Percent"];
const COMPARISONS = ["==", "!=", ">=", "<=", ">", "<"];
const OPERATOR_TO_PYTHON = { "=": "==", "!=": "!=" };

/** The list view's builder shape: leaf rows with `and` / `or`, nested lists as parentheses. */
export function toExpression(conditions, fields = []) {
	const parts = [];
	withConjunctions(conditions || []).forEach((item) => {
		if (typeof item === "string") return parts.push(item);
		const clause = isGroup(item) ? groupExpression(item, fields) : clauseFor(item, fields);
		parts.push(clause || "");
	});
	return joinParts(parts);
}

/** A plain list of rows, with no conjunctions between them, means "all of these". */
function withConjunctions(conditions) {
	if (conditions.some((item) => typeof item === "string")) return conditions;
	return conditions.flatMap((item, index) => (index ? ["and", item] : [item]));
}

/** A leaf is [field, operator, value]; a group holds conditions, so it starts with one. */
function isGroup(item) {
	return Array.isArray(item) && Array.isArray(item[0]);
}

function groupExpression(item, fields) {
	const inner = toExpression(item, fields);
	return inner ? `(${inner})` : "";
}

/** Drop conjunctions left dangling by a row that produced nothing. */
function joinParts(parts) {
	const kept = [];
	parts.forEach((part) => {
		const conjunction = part === "and" || part === "or";
		if (!part) return;
		if (conjunction && !kept.length) return;
		if (conjunction && (kept.at(-1) === "and" || kept.at(-1) === "or")) return;
		kept.push(part);
	});
	if (kept.at(-1) === "and" || kept.at(-1) === "or") kept.pop();
	return kept.join(" ");
}

export function toFilters(expression) {
	const text = String(expression || "").trim();
	if (!text) return [];
	const parts = splitTopLevel(text);
	if (!parts) return null;
	const parsed = parts.map((part) => {
		if (part === "and" || part === "or") return part;
		// `expandGroups` already turned a parenthesised part into its own condition list.
		return Array.isArray(part) ? part : parseClause(part);
	});
	return parsed.every(Boolean) ? parsed : null;
}

/** Split on `and` / `or` that sit outside any parentheses; parenthesised groups recurse. */
function splitTopLevel(text) {
	const parts = [];
	let depth = 0;
	let current = "";
	let quote = "";
	for (let index = 0; index < text.length; index++) {
		const char = text[index];
		if (quote) {
			if (char === quote) quote = "";
			current += char;
			continue;
		}
		if (char === '"' || char === "'") quote = char;
		if (char === "(") depth++;
		if (char === ")") depth--;
		const keyword = depth === 0 && matchKeyword(text, index);
		if (!keyword) {
			current += char;
			continue;
		}
		parts.push(current.trim(), keyword);
		current = "";
		index += keyword.length;
	}
	parts.push(current.trim());
	return depth === 0 ? expandGroups(parts.filter(Boolean)) : null;
}

function matchKeyword(text, index) {
	const before = index === 0 || /\s/.test(text[index - 1]);
	if (!before) return null;
	return ["and", "or"].find(
		(word) => text.startsWith(word, index) && /\s/.test(text[index + word.length] || "")
	);
}

function expandGroups(parts) {
	const expanded = [];
	for (const part of parts) {
		if (part === "and" || part === "or") {
			expanded.push(part);
			continue;
		}
		if (!part.startsWith("(") || !part.endsWith(")")) {
			expanded.push(part);
			continue;
		}
		const inner = toFilters(part.slice(1, -1));
		if (!inner) return null;
		expanded.push(inner);
	}
	return expanded;
}

/** Whether the filter UI can represent this expression without losing anything. */
export function isFilterExpression(expression) {
	return toFilters(expression) !== null;
}

/** A one-line reading of a condition, for canvas nodes and the read-only view. */
export function summarizeCondition(expression) {
	const conditions = toFilters(expression);
	if (!conditions) return String(expression || "");
	return describeConditions(conditions);
}

function describeConditions(conditions) {
	return conditions
		.map((item) => {
			if (typeof item === "string") return item === "or" ? __("or") : __("and");
			return isGroup(item) ? `(${describeConditions(item)})` : describeFilter(item);
		})
		.join(" ");
}

const PHRASES = {
	"=": (field, value) => __("{0} is {1}", [field, value]),
	"!=": (field, value) => __("{0} is not {1}", [field, value]),
	in: (field, value) => __("{0} is one of {1}", [field, value]),
	"not in": (field, value) => __("{0} is none of {1}", [field, value]),
	like: (field, value) => __("{0} contains {1}", [field, value]),
	"not like": (field, value) => __("{0} does not contain {1}", [field, value]),
};

function describeFilter([fieldname, operator, value]) {
	const field = prettyField(fieldname);
	if (operator === "is")
		return value === "set" ? __("{0} is set", [field]) : __("{0} is empty", [field]);
	const phrase = PHRASES[operator];
	const text = Array.isArray(value) ? value.join(", ") : String(value ?? "");
	return phrase ? phrase(field, text) : `${field} ${operator} ${text}`;
}

function prettyField(fieldname) {
	const words = String(fieldname || "").replace(/_/g, " ");
	return words.charAt(0).toUpperCase() + words.slice(1);
}

function clauseFor(filter, fields) {
	const [fieldname, operator, value] = filter;
	if (operator === "is") return presenceClause(fieldname, value);
	if (operator === "like" || operator === "not like")
		return containsClause(fieldname, operator, value);
	if (operator === "in" || operator === "not in")
		return listClause(fieldname, operator, value, fields);
	const comparison = OPERATOR_TO_PYTHON[operator] || operator;
	if (!COMPARISONS.includes(comparison)) return "";
	return `doc.${fieldname} ${comparison} ${literal(value, fieldname, fields)}`;
}

function presenceClause(fieldname, value) {
	const comparison = value === "not set" ? "==" : "!=";
	return `(doc.${fieldname} or "") ${comparison} ""`;
}

function containsClause(fieldname, operator, value) {
	const needle = String(value ?? "")
		.replace(/%/g, "")
		.toLowerCase();
	const membership = operator === "like" ? "in" : "not in";
	return `${quote(needle)} ${membership} (doc.${fieldname} or "").lower()`;
}

function listClause(fieldname, operator, value, fields) {
	const items = (Array.isArray(value) ? value : splitValues(value)).map((item) =>
		literal(item, fieldname, fields)
	);
	return `doc.${fieldname} ${operator} [${items.join(", ")}]`;
}

function literal(value, fieldname, fields) {
	if (typeof value === "number") return String(value);
	const text = String(value ?? "");
	const field = fields.find((item) => item.fieldname === fieldname);
	const numeric = NUMERIC_FIELDTYPES.includes(field?.fieldtype) || field?.fieldtype === "Check";
	if (numeric && text !== "" && !Number.isNaN(Number(text))) return text;
	return quote(text);
}

function quote(text) {
	return `"${String(text).replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
}

function splitValues(value) {
	return String(value ?? "")
		.split(",")
		.map((item) => item.trim())
		.filter(Boolean);
}

// --- parsing -------------------------------------------------------------
// Strict on purpose: a looser parse would half-match a hand-written expression and rewrite it.
const LITERAL = `"[^"]*"|'[^']*'|-?\\d+(?:\\.\\d+)?`;
const PRESENCE = /^\(doc\.(\w+) or ""\) (==|!=) ""$/;
const CONTAINS =
	/^"([^"]*)" (not in|in) \(doc\.(\w+) or ""\)\.lower\(\)$|^'([^']*)' (not in|in) \(doc\.(\w+) or ""\)\.lower\(\)$/;
const MEMBERSHIP = new RegExp(
	`^doc\\.(\\w+) (not in|in) \\[((?:${LITERAL})(?:, *(?:${LITERAL}))*)?\\]$`
);
const COMPARISON = new RegExp(`^doc\\.(\\w+) (==|!=|>=|<=|>|<) (${LITERAL})$`);

function parseClause(clause) {
	return (
		parsePresence(clause) ||
		parseContains(clause) ||
		parseMembership(clause) ||
		parseComparison(clause)
	);
}

function parsePresence(clause) {
	const match = clause.match(PRESENCE);
	if (!match) return null;
	return [match[1], "is", match[2] === "==" ? "not set" : "set"];
}

function parseContains(clause) {
	const match = clause.match(CONTAINS);
	if (!match) return null;
	const [value, operator, fieldname] =
		match[1] === undefined ? [match[4], match[5], match[6]] : [match[1], match[2], match[3]];
	return [fieldname, operator === "in" ? "like" : "not like", unquote(value)];
}

function parseMembership(clause) {
	const match = clause.match(MEMBERSHIP);
	if (!match) return null;
	const items = String(match[3] || "")
		.split(",")
		.map((item) => parseLiteral(item.trim()))
		.filter((item) => item !== "");
	return [match[1], match[2], items];
}

function parseComparison(clause) {
	const match = clause.match(COMPARISON);
	if (!match) return null;
	const operator = match[2] === "==" ? "=" : match[2];
	return [match[1], operator, parseLiteral(match[3].trim())];
}

/** Conditions written by hand or seeded from Python use either quote style. */
function parseLiteral(text) {
	if (/^".*"$/.test(text) || /^'.*'$/.test(text)) return unquote(text.slice(1, -1));
	if (text === "") return "";
	return Number.isNaN(Number(text)) ? text : Number(text);
}

function unquote(text) {
	return text.replace(/\\"/g, '"').replace(/\\\\/g, "\\");
}
