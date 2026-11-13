// The page's side of Customize's header acts: the dialogs they ask with.
import { __ } from "@/i18n";
import { shellDialog } from "@/shell/dialog";
import type { CustomizeHost } from "./customizeActs";
import type { EditorState } from "./editorSource";
import ExportCustomizationsDialog from "./ExportCustomizationsDialog.vue";
import ResetAllDialog from "./ResetAllDialog.vue";

export function customizeHost(page: {
	state: () => EditorState | null;
	dirty: () => boolean;
	developerMode: boolean;
	setMode: CustomizeHost["setMode"];
	reload: CustomizeHost["reload"];
}): CustomizeHost {
	return {
		developerMode: page.developerMode,
		setMode: page.setMode,
		reload: page.reload,
		askReset: (counts) => {
			const { doctype, app_title } = page.state()!;
			return shellDialog().open(
				ResetAllDialog,
				{ doctype, appTitle: app_title, counts, dirty: page.dirty() },
				{ title: __("Reset {0}?", [doctype]) }
			);
		},
		askExport: () => {
			const { doctype, module } = page.state()!;
			return shellDialog().open(
				ExportCustomizationsDialog,
				{ doctype, module },
				{ title: __("Export customizations") }
			);
		},
	};
}
