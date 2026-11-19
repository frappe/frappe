// A child table's fields for the parent's editor: as the child's open editor has them, else as
// its saved meta has them, and whether that meta is still loading or failed.
import { computed, inject, type ComputedRef } from "vue";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { CHILD_TABLES } from "./childTables";

export interface ChildFields {
	fields: ComputedRef<RawMetaField[] | null>;
	loading: ComputedRef<boolean>;
	error: ComputedRef<unknown>;
	reload: () => void;
}

export function useChildFields(doctype: () => string | null | undefined): ChildFields {
	const tables = inject(CHILD_TABLES, null);
	const open = computed(() => {
		const name = doctype();
		return name ? (tables?.fields(name) ?? null) : null;
	});
	const saved = useDoctypeMeta(() => {
		const name = doctype();
		return !name || open.value || tables?.added().includes(name) ? "" : name;
	});
	const fields = computed(() => {
		const name = doctype();
		if (!name) return null;
		if (open.value) return open.value;
		return tables?.added().includes(name) ? [] : (saved.meta.value?.fields ?? null);
	});
	const error = computed(() => (fields.value ? null : saved.error.value));
	const loading = computed(() => Boolean(doctype()) && !fields.value && !error.value);
	return { fields, loading, error, reload: saved.reload };
}
