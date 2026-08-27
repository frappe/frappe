// One field's per-render property override, and the three places it lands.
//
// Ticket 48 built the carrier for the three properties the render path
// *recomputes* (`FieldOverride`). The other properties an app may override are
// computed once, when `mapField` builds the node, and never touched again — so
// they are applied there instead, and a single carrier would have hidden that
// difference behind one flat object that half worked.
import type {
	FieldMeta,
	FieldNode,
	FieldOverride,
	FieldUI,
} from "@framework/ui/components/FormLayout/types";

/**
 * The build-time half: properties `mapField` sets once and nothing recomputes,
 * so overriding them is a plain merge onto the built node.
 *
 * `options` is the one with a caveat — on a `Table` it names the child doctype,
 * and the node's `childFields`/`childLayout` were already resolved from the
 * original. Overriding a `Link`'s target or a `Select`'s choices (what v1's
 * `options` is for) is unaffected.
 */
export type FieldMetaPatch = Pick<
	FieldMeta,
	"label" | "options" | "placeholder" | "description" | "precision" | "filters"
>;

/**
 * Everything an app may override on one field, split by *when* it applies.
 * Plain data throughout: `FormLayout` reads the result off the schema and knows
 * nothing about who wrote it.
 */
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
	// Both halves merge rather than replace: nothing upstream writes `override`
	// today, but a patch that names one key should not silently drop another.
	if (patch.override)
		patched.override = { ...node.override, ...patch.override };
	if (patch.ui) patched.ui = { ...node.ui, ...patch.ui };
	return patched;
}
