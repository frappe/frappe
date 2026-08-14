import type { RawMetaField } from "../../components/FormLayout/types";
import type { FieldAccess } from "../../composables/useDocPermissions";

/**
 * Bake a permlevel decision into a raw meta field: `read` demotes it to
 * read-only, `none` hides it. Applied *before* `mapField`, in DocField
 * vocabulary, so both layout sources hand the same shape forward.
 *
 * The denial is expressed as a plain `hidden` / `read_only` flag — which reads
 * exactly like a meta-hidden or meta-read-only field — so it is also stamped
 * `perm_denied`. That stamp, not the `permlevel`, is what
 * `resolveFieldConditionals` treats as a floor an override may not lift: a
 * reader who *has* the level leaves here untouched, and so must stay
 * overridable.
 *
 * Note this is fail-open while permissions load: `useDocPermissions.fieldAccess`
 * deliberately answers `"write"` until the roles land (better a field the server
 * refuses to save than a form that flashes empty), so during that window nothing
 * is stamped and nothing is floored. It re-joins when they arrive.
 */
export function withAccess(
	field: RawMetaField,
	fieldAccess?: (field: RawMetaField) => FieldAccess
): RawMetaField {
	const access = fieldAccess?.(field);
	if (!access || access === "write") return field;
	return access === "read"
		? { ...field, read_only: 1, perm_denied: 1 }
		: { ...field, hidden: 1, perm_denied: 1 };
}
