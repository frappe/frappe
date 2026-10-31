// One field's per-render property override, split by when each half applies.
import type {
	FieldMeta,
	FieldNode,
	FieldOverride,
	FieldUI,
	FormLayoutSchema,
} from "@framework/ui/FormLayout/types";

/**
 * The build-time half: properties `mapField` sets once. `options` on a `Table` names
 * the child doctype, whose `childFields`/`childLayout` were already resolved from the original.
 */
export type FieldMetaPatch = Pick<
	FieldMeta,
	| "label"
	| "options"
	| "placeholder"
	| "description"
	| "precision"
	| "filters"
	| "cannotAddRows"
	| "cannotDeleteRows"
>;

/** Everything an app may override on one field, split by when it applies. Plain data throughout. */
export interface FieldPatch {
	/** Merged onto the built node (see `FieldMetaPatch`). */
	meta?: FieldMetaPatch;
	/** The three the render path recomputes; applied last, after `depends_on`. */
	override?: FieldOverride;
	/** Presentation overlay, merged over whatever `decorate` contributed. */
	ui?: FieldUI;
}

/** Apply a patch to a freshly built node, returning a new node. */
export function applyFieldPatch(
	node: FieldNode,
	patch: FieldPatch | undefined
): FieldNode {
	if (!patch) return node;
	const patched: FieldNode = { ...node, ...patch.meta };
	// Both halves merge, so a patch naming one key does not silently drop another.
	if (patch.override)
		patched.override = { ...node.override, ...patch.override };
	if (patch.ui) patched.ui = { ...node.ui, ...patch.ui };
	return patched;
}

/** A table's column patches by child fieldname, from overrides keyed `<table>.<column>`. */
export function columnPatches(
	overrides: Record<string, FieldPatch> | undefined,
	table: string
): Map<string, FieldPatch> {
	const prefix = `${table}.`;
	const patches = new Map<string, FieldPatch>();
	for (const [name, patch] of Object.entries(overrides ?? {}))
		if (name.startsWith(prefix)) patches.set(name.slice(prefix.length), patch);
	return patches;
}

/** Apply column patches to a table node's grid columns and its row form. */
export function applyColumnPatches(node: FieldNode, patches: Map<string, FieldPatch>): FieldNode {
	if (!patches.size) return node;
	const patch = (column: FieldNode) => applyFieldPatch(column, patches.get(column.fieldname));
	const patched: FieldNode = { ...node };
	if (node.childFields) patched.childFields = node.childFields.map(patch);
	if (node.childLayout) patched.childLayout = mapFields(node.childLayout, patch);
	return patched;
}

function mapFields(
	layout: FormLayoutSchema,
	transform: (field: FieldNode) => FieldNode
): FormLayoutSchema {
	return layout.map((tab) => ({
		...tab,
		sections: tab.sections.map((section) => ({
			...section,
			columns: section.columns.map((column) => ({ ...column, fields: column.fields.map(transform) })),
		})),
	}));
}
