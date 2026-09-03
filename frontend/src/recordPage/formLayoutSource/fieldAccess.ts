import type { RawMetaField } from "@framework/ui/components/FormLayout/types";
import type { FieldAccess } from "@framework/ui/composables/useDocPermissions";

/**
 * Bakes a permlevel decision into a raw meta field before `mapField`: `read` demotes it,
 * `none` hides it, and either stamps `perm_denied`, the floor an override may not lift.
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
