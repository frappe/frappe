// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
// License: MIT. See LICENSE

// Opens the Data Import wizard in a dialog by hosting a real Data Import form inside it.

frappe.provide("frappe.data_import");

frappe.data_import.open_data_import_dialog = function ({
	data_import = null,
	reference_doctype = null,
	import_type = "Insert New Records",
	title = null,
} = {}) {
	if (!data_import && !reference_doctype) {
		frappe.throw(
			__("Pass either an existing {0} name or a {1} to import into.", [
				__("Data Import"),
				__("Reference DocType"),
			])
		);
	}

	// The meta carries the Data Import form script that mounts the wizard.
	frappe.model.with_doctype("Data Import", () => {
		frappe.require("data_import_wizard.bundle.js", () => {
			_open({ data_import, reference_doctype, import_type, title });
		});
	});
};

function _open({ data_import, reference_doctype, import_type, title }) {
	const dialog = new frappe.ui.Dialog({
		title:
			title || (data_import ? __("Data Import") : __("Import {0}", [__(reference_doctype)])),
		size: "extra-large",
		minimizable: true,
	});

	const $host = $('<div class="data-import-dialog-host"></div>').appendTo(dialog.$body);

	// in_form=false: skip rename_notify's set_route so first save doesn't tear down the dialog
	const frm = new frappe.ui.form.Form("Data Import", $host.get(0), false);
	frm.in_dialog = true;
	frm._data_import_dialog = dialog;

	const boot_new = () => {
		// New doc isn't persisted until the wizard saves, so closing without attaching creates no record
		const name = frappe.model.make_new_doc_and_get_name("Data Import");
		const doc = frappe.get_doc("Data Import", name);
		doc.reference_doctype = reference_doctype;
		doc.import_type = import_type;
		frm.refresh(name);
	};

	const boot_existing = () => {
		frappe.model.with_doc("Data Import", data_import, (name, r) => {
			if (r && r["403"]) {
				dialog.hide();
				frappe.show_alert({ message: __("Not permitted"), indicator: "red" });
				return;
			}
			frm.refresh(data_import);
		});
	};

	dialog.$wrapper.addClass("data-import-dialog");
	dialog.show();

	// Instantiate after show so the host has layout (make_app_page/measurements are happier).
	if (data_import) {
		boot_existing();
	} else {
		boot_new();
	}

	// Cleanup: unmount the wizard + drop the embedded form's global side effects.
	dialog.$wrapper.on("hide.bs.modal", () => {
		try {
			frm._data_import_wizard?.unmount?.();
		} catch (e) {
			// ignore
		}
		for (const [event, handler] of frm._realtime_handlers || []) {
			frappe.realtime.off(event, handler);
		}
		const grid = frm.fields_dict.value_mappings?.grid;
		if (grid?._value_mapping_scroll_handler) {
			document.removeEventListener("scroll", grid._value_mapping_scroll_handler, true);
		}
		removeEventListener("beforeunload", frm.beforeUnloadListener, { capture: true });
		if (window.cur_frm === frm) window.cur_frm = null;
	});
}
