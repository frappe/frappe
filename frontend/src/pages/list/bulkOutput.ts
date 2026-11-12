// Edit, Export and Copy on the selection, the same for every renderer: the dialogs' state, the edit's
// request and the copy. Part of the bulk bar's lazy chunk.
import type { BulkSelection, BulkUpdate } from "@framework/ui/api";
import { toast } from "frappe-ui";
import { ref, type Ref } from "vue";
import { __, __n } from "@/i18n";
import { selectionTsv, withHiddenRows } from "@/list/bulkCopy";
import type { ListRow } from "@/list/useListRows";
import { errorMessage } from "@/recordPage/errorMessage";
import type { BulkBarOptions } from "./useBulkBar";

export interface BulkOutput {
	/** The Edit dialog: open, and mounted since it was first asked for. */
	edit: { open: Ref<boolean>; mounted: Ref<boolean> };
	/** The Export dialog, and the selection as it was when it was asked for. */
	export: { open: Ref<boolean>; mounted: Ref<boolean>; selection: Ref<BulkSelection> };
	askEdit: () => void;
	askExport: () => void;
	runEdit: (update: BulkUpdate) => Promise<void>;
	copy: () => void;
}

export function useBulkOutput(options: BulkBarOptions): BulkOutput {
	const { doctype, scope, selection } = options;
	const edit = { open: ref(false), mounted: ref(false) };
	const exported = { open: ref(false), mounted: ref(false), selection: ref<BulkSelection>({ names: [] }) };

	function askEdit() {
		edit.mounted.value = true;
		edit.open.value = true;
	}

	function askExport() {
		exported.selection.value = scope.selected();
		exported.mounted.value = true;
		exported.open.value = true;
	}

	async function runEdit(update: BulkUpdate) {
		const { updateRows } = await import("@/list/bulkEdit");
		await updateRows(doctype, { reload: options.reload }, scope.selected(), update, (names) => {
			scope.clear();
			selection.value = names;
		});
		scope.clear();
	}

	function copy() {
		const names = [...selection.value];
		const chosen = new Set(names);
		const loaded = options.rows.value.filter((row): row is ListRow => chosen.has(row.name));
		const { columns, text, fields } = options.copy;
		let copied = loaded.length;
		const tsv = (picked: Record<string, unknown>[]) => {
			copied = picked.length;
			return selectionTsv(columns(), picked, text);
		};
		let readError: unknown;
		const withHidden = () =>
			withHiddenRows(doctype, names, loaded, fields())
				.then((picked) => new Blob([tsv(picked)], { type: "text/plain" }))
				.catch((error) => {
					readError = error;
					throw error;
				});
		// `navigator.clipboard` is missing on a non-secure origin; writing in the click keeps its user
		// activation, and a ClipboardItem holding a promise keeps it across the read of hidden rows.
		Promise.resolve()
			.then(() =>
				loaded.length === names.length
					? navigator.clipboard.writeText(tsv(loaded))
					: navigator.clipboard.write([new ClipboardItem({ "text/plain": withHidden() })])
			)
			.then(() => toast.success(__n("Copied {0} row", "Copied {0} rows", copied, [copied])))
			.catch(() => toast.error(readError ? errorMessage(readError) : __("The browser did not allow copying.")));
	}

	return { edit, export: exported, askEdit, askExport, runEdit, copy };
}
