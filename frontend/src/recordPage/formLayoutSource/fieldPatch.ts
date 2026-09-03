// One field's per-render property override, split by when each half applies.
import type {
	FieldMeta,
	FieldNode,
	FieldOverride,
	FieldUI,
} from "@framework/ui/components/FormLayout/types";

/**
 * The build-time half: properties `mapField` sets once. `options` on a `Table` names
 * the child doctype, whose `childFields`/`childLayout` were already resolved from the original.
 */
export type FieldMetaPatch = Pick<
	FieldMeta,
	"label" | "options" | "placeholder" | "description" | "precision" | "filters"
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
