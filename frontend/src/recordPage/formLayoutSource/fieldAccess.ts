import { NO_VALUE } from "@framework/ui/FormLayout/noValueFields";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import type { FieldAccess } from "@framework/ui/useDocPermissions";

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

/**
 * What the server lets a person write at this `docstatus`: on a submitted record only the
 * `allow_on_submit` fields they could already write, on a cancelled one none.
 */
export function accessAtDocstatus(
	access: FieldAccess,
	field: Pick<RawMetaField, "fieldtype" | "allow_on_submit">,
	docstatus: number | undefined,
): FieldAccess {
	if (access !== "write" || !docstatus || NO_VALUE.has(field.fieldtype)) return access;
	return docstatus === 1 && field.allow_on_submit ? "write" : "read";
}
