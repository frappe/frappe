// A stored rule in words, for its panel row, its Tooltip and the canvas mark: "Always", "Status is
// Open and Paid is on", or the code as written when the builder cannot read it.
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import {
	dependsOnScope,
	fromDependsOn,
	isGroup,
	referencedField,
	toDependsOn,
	type ConditionField,
	type ConditionGroup,
	type DependsOnScope,
	type FieldConditionValue,
} from "@framework/ui/ConditionBuilder";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import type { RuleCodec } from "./ruleDraft";
import { ruleValue, type RuleRow } from "./ruleRows";

export type Leaf = FieldConditionValue;
export type RuleTree = ConditionGroup<Leaf>;

export interface RuleSummary {
	kind: "empty" | "rules" | "code";
	text: string;
}

/** What a row's words need to know of the fields it names. */
export interface LeafContext {
	field(fieldname: string): ConditionField | undefined;
	label(fieldname: string): string;
	table(fieldname: string): boolean;
	/** A value naming a field: its label in a condition, "this record's …" in a link filter. */
	reference(fieldname: string): string;
	/** A condition compares two fields ("is the same as"); a filter shows the reference as a value. */
	comparesFields: boolean;
}

const RECORD_IS_NEW = "__islocal";
const DOCUMENT_STATUS = "docstatus";
const MADE = new WeakMap<object, RuleWords>();

/** The conditions of one DocType's fields, read with ui's converter. */
export class RuleWords implements LeafContext, RuleCodec {
	readonly scope: DependsOnScope;
	readonly comparesFields = true;
	private labels: Map<string, string>;

	/** One per working state, shared by the panel and every canvas mark. A child DocType's parent is
	 *  not known to the editor (it may sit in many), so it offers no parent fields. */
	static of(canvas: DesignCanvas): RuleWords {
		const working = canvas.working.value;
		let words = MADE.get(working);
		if (!words) {
			words = new RuleWords(working.fields, { submittable: Boolean(canvas.state.definition.is_submittable) });
			MADE.set(working, words);
		}
		return words;
	}

	constructor(fields: RawMetaField[], options: { submittable?: boolean } = {}) {
		this.scope = dependsOnScope(fields, options);
		this.labels = new Map(fields.map((field) => [field.fieldname, field.label || field.fieldname]));
	}

	say(raw: string | null | undefined, empty: string): RuleSummary {
		const tree = this.read(raw);
		if (!tree) return { kind: "code", text: codeOf(raw ?? "") };
		if (!tree.conditions.length) return { kind: "empty", text: empty };
		return { kind: "rules", text: sayGroup(tree, this, false) };
	}

	/** The row's Tooltip and the canvas mark's line; empty when the rule is. */
	sentence(rule: RuleRow, raw: string | null | undefined): string {
		const said = this.say(raw, "");
		if (said.kind === "empty") return "";
		if (said.kind === "code") return __("{0} (code): {1}", [__(rule.label), said.text]);
		return __(rule.sentence, [said.text]);
	}

	/** The canvas mark's Tooltip: the sentence of each rule set on the field or container. */
	lines(rules: RuleRow[], node: object): string[] {
		return rules.map((rule) => this.sentence(rule, ruleValue(node, rule))).filter(Boolean);
	}

	/** The rule as a builder tree; null when only code can show it as written. */
	read(raw: string | null | undefined): RuleTree | null {
		return fromDependsOn(raw, this.scope);
	}

	write(tree: RuleTree): string {
		return toDependsOn(tree, this.scope);
	}

	code(raw: string): string {
		return codeOf(raw);
	}

	/** `eval:` goes back only on code shown from an `eval:` rule: `fn:` and bare fieldnames stay as typed. */
	fromCode(text: string, shownFrom: string): string {
		const code = text.trim();
		if (!code) return "";
		return shownFrom === "" || shownFrom.startsWith("eval:") ? `eval:${code}` : code;
	}

	/** The fields a value may name: not a table, nor the record's own "fields". */
	referable(): ConditionField[] {
		return this.scope.fields.filter(
			(one) => !this.table(one.fieldname) && one.fieldname !== RECORD_IS_NEW && one.fieldname !== DOCUMENT_STATUS,
		);
	}

	field(fieldname: string) {
		return this.scope.fields.find((one) => one.fieldname === fieldname);
	}

	label(fieldname: string) {
		return this.labels.get(fieldname) ?? this.field(fieldname)?.label ?? fieldname;
	}

	table(fieldname: string) {
		return this.scope.tables.has(fieldname);
	}

	reference(fieldname: string) {
		return this.label(fieldname);
	}
}

/** The code after `eval:`, which is what the Code tab edits. */
export function codeOf(raw: string): string {
	return raw.startsWith("eval:") ? raw.slice(5) : raw;
}

export function sayGroup(group: RuleTree, context: LeafContext, nested: boolean): string {
	const parts = group.conditions.map((node) =>
		isGroup(node) ? sayGroup(node as RuleTree, context, true) : sayLeaf(node as Leaf, context),
	);
	const joined = parts.reduce((said, next) =>
		group.conjunction === "or" ? __("{0} or {1}", [said, next]) : __("{0} and {1}", [said, next]),
	);
	return nested && parts.length > 1 ? `(${joined})` : joined;
}

export function sayLeaf(leaf: Leaf, context: LeafContext): string {
	const label = context.label(leaf.fieldname);
	const field = context.field(leaf.fieldname);
	if (field?.fieldtype === "Check" && (leaf.value === "Yes" || leaf.value === "No")) {
		return sayCheck(leaf, label, context.table(leaf.fieldname));
	}
	const named = referencedField(leaf.value);
	const value = sayValue(leaf, context);
	switch (leaf.operator) {
		case "is":
		case "is not":
			return (leaf.operator === "is") === (leaf.value === "set")
				? __("{0} is set", [label])
				: __("{0} is empty", [label]);
		case "equals":
			return named && context.comparesFields
				? __("{0} is the same as {1}", [label, value])
				: __("{0} is {1}", [label, value]);
		case "not equals":
			return named && context.comparesFields
				? __("{0} differs from {1}", [label, value])
				: __("{0} is not {1}", [label, value]);
		case "in":
			return listOf(leaf.value).length > 1
				? __("{0} is one of {1}", [label, value])
				: __("{0} is {1}", [label, value]);
		case "not in":
			return __("{0} is none of {1}", [label, value]);
		case "like":
			return __("{0} contains {1}", [label, value]);
		case "not like":
			return __("{0} does not contain {1}", [label, value]);
		case ">":
			return __("{0} is more than {1}", [label, value]);
		case "<":
			return __("{0} is less than {1}", [label, value]);
		case ">=":
			return __("{0} is at least {1}", [label, value]);
		case "<=":
			return __("{0} is at most {1}", [label, value]);
		case "between": {
			const [from, to] = listOf(leaf.value).map((one) => shown(one, leaf, context));
			return __("{0} is between {1} and {2}", [label, from, to]);
		}
		default:
			return `${label} ${leaf.operator} ${value}`;
	}
}

function sayCheck(leaf: Leaf, label: string, table: boolean): string {
	const on = (leaf.value === "Yes") === (leaf.operator !== "not equals");
	if (leaf.fieldname === RECORD_IS_NEW) return on ? __("Record is new") : __("Record is saved");
	if (table) return on ? __("{0} has rows", [label]) : __("{0} has no rows", [label]);
	return on ? __("{0} is on", [label]) : __("{0} is off", [label]);
}

function sayValue(leaf: Leaf, context: LeafContext): string {
	return listOf(leaf.value)
		.map((one) => shown(one, leaf, context))
		.join(", ");
}

function shown(value: unknown, leaf: Leaf, context: LeafContext): string {
	const named = referencedField(value);
	if (named) return context.reference(named);
	if (leaf.fieldname === DOCUMENT_STATUS) return __(String(value));
	return String(value ?? "");
}

export function listOf(value: unknown): unknown[] {
	if (Array.isArray(value)) return value;
	if (typeof value === "string" && value.includes(",")) return value.split(",").map((one) => one.trim());
	return [value];
}
