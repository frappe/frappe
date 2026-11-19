// The page's side of Customize's header acts: the dialogs they ask with.
import { __ } from "@/i18n";
import { shellDialog } from "@/shell/dialog";
import type { CustomizeHost } from "./customizeActs";
import ExportCustomizationsDialog from "./ExportCustomizationsDialog.vue";
import ResetAllDialog from "./ResetAllDialog.vue";

export function customizeHost(page: {
	dirty: () => boolean;
	developerMode: boolean;
	setMode: CustomizeHost["setMode"];
	reload: CustomizeHost["reload"];
}): CustomizeHost {
	return {
		developerMode: page.developerMode,
		setMode: page.setMode,
		reload: page.reload,
		askReset: ({ doctype, app_title }, counts) =>
			shellDialog().open(
				ResetAllDialog,
				{ doctype, appTitle: app_title, counts, dirty: page.dirty() },
				{ title: __("Reset {0}?", [doctype]) }
			),
		askExport: ({ doctype, module }, changes) =>
			shellDialog().open(
				ExportCustomizationsDialog,
				{ doctype, module, changes },
				{ title: __("Export customizations") }
			),
	};
}
