// The page's side of the Danger zone's acts: the question about pending edits, and the dialogs.
import { toast } from "frappe-ui";
import { defineAsyncComponent, type Component } from "vue";
import { __ } from "@/i18n";
import { shellDialog } from "@/shell/dialog";
import type { DangerHost } from "./dangerActs";
import { confirmModeSwitch } from "./modeSwitch";
import ModeSwitchDialog from "./ModeSwitchDialog.vue";
import { kindOf } from "./settingsRows";

// Each dialog loads when it first opens: the editor's page JS does not carry them.
const ChangeKindDialog = lazy(() => import("./ChangeKindDialog.vue"));
const RenameDoctypeDialog = lazy(() => import("./RenameDoctypeDialog.vue"));
const ModuleDialog = lazy(() => import("./ModuleDialog.vue"));
const DeleteDoctypeDialog = lazy(() => import("./DeleteDoctypeDialog.vue"));

interface DangerPage extends Pick<DangerHost, "scope" | "reload" | "renamed" | "deleted" | "showing"> {
	dirty: () => boolean;
	/** Saves the pending edits; true once none are left. */
	save: () => Promise<boolean>;
	/** Drops the pending edits. */
	discard: () => void;
}

export function dangerHost(page: DangerPage): DangerHost {
	return {
		scope: page.scope,
		reload: page.reload,
		renamed: page.renamed,
		deleted: page.deleted,
		showing: page.showing,
		settle: () => settle(page),
		askKind: ({ doctype, definition, record_count }) =>
			shellDialog().open(
				ChangeKindDialog,
				{ doctype, kind: kindOf(definition), records: record_count },
				{ title: __("Change {0}'s kind", [doctype]) }
			),
		askName: ({ doctype, record_count }) =>
			shellDialog().open(RenameDoctypeDialog, { doctype, records: record_count ?? null }, { title: __("Rename {0}", [doctype]) }),
		askModule: ({ doctype, module, custom }, standard) =>
			shellDialog().open(
				ModuleDialog,
				{ doctype, module, custom: Boolean(custom), standard },
				{ title: standard ? __("Make {0} standard", [doctype]) : __("Move {0}", [doctype]) }
			),
		askDelete: ({ doctype, record_count }) =>
			shellDialog().open(
				DeleteDoctypeDialog,
				{ doctype, records: record_count },
				{ title: __("Delete {0}?", [doctype]) }
			),
	};
}

/** Save first, Discard or Cancel, as the Design | Customize switch asks. */
async function settle(page: DangerPage): Promise<boolean> {
	const go = await confirmModeSwitch({
		dirty: page.dirty(),
		ask: () =>
			shellDialog().open(
				ModeSwitchDialog,
				{ message: __("This DocType has changes that are not saved.") },
				{ title: __("Save before you go on?") }
			),
		save: page.save,
	});
	// Saved or discarded: either way nothing stays pending, even when the act's dialog is cancelled.
	if (go) page.discard();
	return go;
}

function lazy(loader: () => Promise<{ default: Component }>) {
	return defineAsyncComponent({
		loader,
		onError: (_error, _retry, fail) => {
			toast.error(__("The dialog did not load. Reload the page and try again."));
			fail();
		},
	});
}
