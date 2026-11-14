// A Link field's `link_filters`: a flat AND list `[[doctype, fieldname, operator, value], ...]`, as
// JSON, against the target DocType's fields. A value `eval:doc.x` is a field of this record.
import { emptyTree, isGroup, type ConditionField, type ConditionOperator } from "@framework/ui/ConditionBuilder";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { __ } from "@/i18n";
import type { RuleCodec } from "./ruleDraft";
import {
	listOf,
	sayGroup,
	type Leaf,
	type LeafContext,
	type RuleSummary,
	type RuleTree,
	type RuleWords,
} from "./ruleWords";

const WIRE: Partial<Record<ConditionOperator, string>> = {
	equals: "=",
	"not equals": "!=",
	like: "like",
	"not like": "not like",
	in: "in",
	"not in": "not in",
	is: "is",
	"<": "<",
	">": ">",
	"<=": "<=",
	">=": ">=",
	between: "between",
};
const FROM_WIRE: Record<string, ConditionOperator> = {
	...Object.fromEntries(Object.entries(WIRE).map(([operator, wire]) => [wire, operator])),
	"==": "equals",
	LIKE: "like",
	"NOT LIKE": "not like",
};
const NUMERIC = ["Int", "Float", "Currency", "Percent", "Rating"];

export class LinkFilters implements LeafContext, RuleCodec {
	readonly comparesFields = false;

	constructor(
		readonly doctype: string,
		readonly fields: ConditionField[],
		/** This record's fields, which a value may name. */
		private record: RuleWords,
	) {}

	/** The filters as a tree; null when only code can show them as written. */
	read(raw: string | null | undefined): RuleTree | null {
		const text = (raw ?? "").trim();
		if (!text) return emptyTree();
		try {
			const rows: unknown = JSON.parse(text);
			if (!Array.isArray(rows)) return null;
			const conditions = rows.map((row) => this.readRow(row));
			// write() drops a row with no value, so such a list stays code.
			if (!conditions.every(finished)) return null;
			return { conjunction: "and", conditions };
		} catch {
			return null;
		}
	}

	/** Unfinished rows are dropped; no filters write "". */
	write(tree: RuleTree): string {
		const rows = tree.conditions.filter((node): node is Leaf => !isGroup(node) && finished(node as Leaf));
		if (!rows.length) return "";
		return JSON.stringify(rows.map((leaf) => this.writeRow(leaf)));
	}

	/** One row per line, so a long list reads in the Code tab. */
	code(raw: string): string {
		const rows = parsed(raw);
		if (!Array.isArray(rows)) return raw;
		return rows.length ? `[\n${rows.map((row) => `  ${rowCode(row)}`).join(",\n")}\n]` : "";
	}

	/** Valid JSON is stored compact; anything else as typed, which the save then refuses. */
	fromCode(text: string): string {
		const rows = parsed(text);
		if (!Array.isArray(rows)) return text.trim();
		return rows.length ? JSON.stringify(rows) : "";
	}

	say(raw: string | null | undefined): RuleSummary {
		const tree = this.read(raw);
		if (!tree) return { kind: "code", text: (raw ?? "").trim() };
		if (!tree.conditions.length) return { kind: "empty", text: __("All {0}", [allOf(this.doctype)]) };
		return { kind: "rules", text: sayGroup(tree, this, false) };
	}

	sentence(raw: string | null | undefined): string {
		const said = this.say(raw);
		if (said.kind === "empty") return "";
		return said.kind === "code" ? __("Filters (code): {0}", [said.text]) : __("Filters: {0}", [said.text]);
	}

	field(fieldname: string) {
		return this.fields.find((one) => one.fieldname === fieldname);
	}

	label(fieldname: string) {
		return this.field(fieldname)?.label ?? fieldname;
	}

	table() {
		return false;
	}

	reference(fieldname: string) {
		return __("this record's {0}", [this.record.label(fieldname)]);
	}

	private readRow(row: unknown): Leaf {
		if (!Array.isArray(row) || row.length !== 4 || row[0] !== this.doctype) throw new Error("Not a link filter");
		const [, fieldname, wire, stored] = row;
		const operator = FROM_WIRE[String(wire)];
		const field = this.field(fieldname);
		if (!operator || !field) throw new Error("Unknown operator or field");
		if (field.fieldtype === "Check" && operator === "equals") {
			if (![0, 1, "0", "1"].includes(stored)) throw new Error("Not a Check value");
			return { fieldname, operator, value: Number(stored) ? "Yes" : "No" };
		}
		const value = Array.isArray(stored) ? stored.map(String) : String(stored ?? "");
		if (operator.includes("like")) {
			if (typeof value !== "string" || !/^%[^%]*%$/.test(value)) throw new Error("Not a contains value");
			return { fieldname, operator, value: value.slice(1, -1) };
		}
		return { fieldname, operator, value };
	}

	/** A Link search keeps one filter per field, so a second one on a field would replace the first. */
	problem(tree: RuleTree): string {
		const seen = new Set<string>();
		for (const node of tree.conditions) {
			if (isGroup(node) || !finished(node as Leaf)) continue;
			const { fieldname } = node as Leaf;
			if (seen.has(fieldname)) {
				return __("{0} has two filters, and a Link search keeps only one. Use one filter, such as Between.", [
					this.label(fieldname),
				]);
			}
			seen.add(fieldname);
		}
		return "";
	}

	private writeRow(leaf: Leaf): unknown[] {
		// The query engines know "is" but not "is not": "is not set" is stored as "is", "not set".
		if (leaf.operator === "is not") {
			return [this.doctype, leaf.fieldname, "is", leaf.value === "set" ? "not set" : "set"];
		}
		const field = this.field(leaf.fieldname);
		return [this.doctype, leaf.fieldname, WIRE[leaf.operator] ?? leaf.operator, this.stored(leaf, field)];
	}

	private stored(leaf: Leaf, field: ConditionField | undefined): unknown {
		const { operator, value } = leaf;
		if (field?.fieldtype === "Check" && operator === "equals") return value === "Yes" ? 1 : 0;
		if (operator === "like" || operator === "not like") return `%${value}%`;
		if (operator === "in" || operator === "not in" || operator === "between") return listOf(value).map(String);
		const reference = typeof value === "string" && value.startsWith("eval:");
		if (field && NUMERIC.includes(field.fieldtype) && !reference && value !== "" && !Number.isNaN(Number(value))) {
			return Number(value);
		}
		return value;
	}
}

/** A Link's new target drops its filters, which name the old target's fields. */
export function targetChange(field: RawMetaField, doctype: string): Record<string, unknown> {
	return field.link_filters ? { options: doctype, link_filters: "" } : { options: doctype };
}

function rowCode(row: unknown): string {
	return Array.isArray(row) ? `[${row.map((one) => JSON.stringify(one)).join(", ")}]` : JSON.stringify(row);
}

function parsed(text: string): unknown {
	try {
		return JSON.parse(text.trim() || "[]");
	} catch {
		return null;
	}
}

function finished(leaf: Leaf): boolean {
	if (!leaf.fieldname) return false;
	const value = leaf.value;
	return !(value === "" || value === null || (Array.isArray(value) && !value.length));
}

/** "Customer" to "customers" in English; a translated name stays as translated. */
function allOf(doctype: string): string {
	const name = __(doctype);
	if (name !== doctype) return name;
	const word = name.toLowerCase();
	if (/[^aeiou]y$/.test(word)) return `${word.slice(0, -1)}ies`;
	if (/(s|x|ch|sh)$/.test(word)) return `${word}es`;
	return `${word}s`;
}
