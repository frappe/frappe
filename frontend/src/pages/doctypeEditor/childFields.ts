// A child table's fields for the parent's editor: as the child's open editor has them, else as
// its saved meta has them.
import { computed, inject, type ComputedRef } from "vue";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { CHILD_TABLES } from "./childTables";

export function useChildFields(doctype: () => string | null | undefined): ComputedRef<RawMetaField[] | null> {
	const tables = inject(CHILD_TABLES, null);
	const open = computed(() => {
		const name = doctype();
		return name ? (tables?.fields(name) ?? null) : null;
	});
	const saved = useDoctypeMeta(() => {
		const name = doctype();
		return !name || open.value || tables?.added().includes(name) ? "" : name;
	});
	return computed(() => {
		const name = doctype();
		if (!name) return null;
		if (open.value) return open.value;
		return tables?.added().includes(name) ? [] : (saved.meta.value?.fields ?? null);
	});
}
