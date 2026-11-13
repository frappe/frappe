// The parent editor's page side of its child tables: `&table=<Table fieldname>` opens the child's
// editor in place, the crumbs lead back, and the child registry is provided to the panel.
import { computed, provide, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { toast } from "frappe-ui";
import { errorMessage } from "@/recordPage/errorMessage";
import { ChildTables, CHILD_TABLES } from "./childTables";
import type { DesignCanvas } from "./designCanvas";
import type { PendingEdits } from "./pendingEdits";

export function useChildTables(edits: PendingEdits, parent: () => DesignCanvas | null) {
	const route = useRoute();
	const router = useRouter();
	const tables = new ChildTables(edits, parent);
	provide(CHILD_TABLES, tables);
	const session = computed(() => tables.open.value);
	/** The canvas the page shows and its acts edit: the open child table's, else the parent's. */
	const shown = computed(() => session.value?.canvas ?? parent());

	watch(
		[() => route.query.table, parent],
		([table]) => {
			tables.show(typeof table === "string" ? table : null).catch((error) => toast.error(errorMessage(error)));
		},
		{ immediate: true },
	);

	/** Opens the child of the parent's Table field `table`, or the parent for `null`; only `table` changes in the address. */
	function open(table: string | null) {
		if ((route.query.table ?? null) === table) return;
		const { table: _open, ...query } = route.query;
		void router.push({ query: table ? { ...query, table } : query });
	}

	/** Opens the editor an undo or redo steps back into: the child's for `doctype`, else the parent's. */
	function reopen(doctype?: string) {
		open(doctype ? tables.tableOf(doctype) : null);
	}

	/** Opens the child editor that holds `doctype`; its canvas, or null when no Table field holds it. */
	async function showChild(doctype: string): Promise<DesignCanvas | null> {
		const table = tables.tableOf(doctype);
		if (!table) return null;
		await tables.show(table);
		open(table);
		return tables.open.value?.canvas ?? null;
	}

	const crumbs = computed(() => {
		const session = tables.open.value;
		if (!session) return [];
		const field = parent()?.field(session.table);
		const back = () => {
			open(null);
			parent()?.select({ kind: "field", fieldname: session.table });
		};
		return [{ label: field?.label || session.table, onClick: back }, { label: session.state.doctype }];
	});

	const tableLabel = computed(() => crumbs.value[0]?.label ?? session.value?.table ?? "");

	return { tables, session, shown, open, reopen, showChild, crumbs, tableLabel };
}
