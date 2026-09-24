// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
// License: MIT. See LICENSE

/**
 * Open the full Data Import wizard inside a Dialog.
 *
 * The wizard is a pure consumer of a live `frm` (it reparents the form's own field
 * wrappers and drives everything through `frm.doc` / `frm.save` / `frm.events.*`).
 * So we don't lift the wizard out of the form — we host a real, embedded Data Import
 * form inside the dialog body. `frappe.ui.form.Form.setup()` calls
 * `frappe.ui.make_app_page({ parent })`, which builds a genuine `frm.page` inside any
 * wrapper (including a dialog body), and `refresh()` runs the "Data Import" controller
 * (loaded from `meta.__js`) which mounts the wizard.
 *
 * Usage:
 *   // Existing Data Import — fetch and show, behaves exactly like the full-page tool:
 *   frappe.data_import.open_data_import_dialog({ data_import: "DATA-IMPORT-0001" });
 *
 *   // New import — user uploads a file and proceeds normally:
 *   frappe.data_import.open_data_import_dialog({
 *       reference_doctype: "Customer",
 *       import_type: "Insert New Records", // or "Update Existing Records"
 *       on_import_complete: (frm) => frappe.msgprint("done"),
 *   });
 */

frappe.provide("frappe.data_import");

frappe.data_import.open_data_import_dialog = function (opts = {}) {
	const {
		data_import = null,
		reference_doctype = null,
		import_type = "Insert New Records",
		title = null,
		on_import_complete = null,
	} = opts;

	if (!data_import && !reference_doctype) {
		frappe.throw(
			__("Pass either an existing {0} name or a {1} to import into.", [
				__("Data Import"),
				__("Reference DocType"),
			])
		);
	}

	// Load the DocType meta first — this also carries the controller script (__js) that
	// registers the "Data Import" form handlers, and the wizard bundle.
	frappe.model.with_doctype("Data Import", () => {
		frappe.require("data_import_wizard.bundle.js", () => {
			_open(opts, {
				data_import,
				reference_doctype,
				import_type,
				title,
				on_import_complete,
			});
		});
	});
};

function _open(opts, { data_import, reference_doctype, import_type, title, on_import_complete }) {
	const dialog = new frappe.ui.Dialog({
		title:
			title || (data_import ? __("Data Import") : __("Import {0}", [__(reference_doctype)])),
		size: "extra-large",
		minimizable: true,
	});

	// A plain wrapper for the embedded form. make_app_page() will attach `.page` here.
	const $host = $('<div class="data-import-dialog-host"></div>').appendTo(dialog.$body);

	// in_form=false: skip rename_notify's set_route so first save doesn't tear down the dialog
	const frm = new frappe.ui.form.Form("Data Import", $host.get(0), false);

	// Let the wizard / controller know it is embedded (so page-context tweaks below
	// and any future in-dialog branches can key off it).
	frm.in_dialog = true;
	frm._data_import_dialog = dialog;

	// Optional: notify caller when the import finishes. The controller flips status to
	// Success/Partial Success; we watch on each refresh.
	if (on_import_complete) {
		frm.__di_notify_complete = () => {
			if (["Success", "Partial Success"].includes(frm.doc?.status) && !frm.__di_notified) {
				frm.__di_notified = true;
				on_import_complete(frm);
			}
		};
	}

	const boot_new = () => {
		// New doc isn't persisted until the wizard saves, so closing without attaching creates no record
		const name = frappe.model.make_new_doc_and_get_name("Data Import");
		const doc = frappe.get_doc("Data Import", name);
		doc.reference_doctype = reference_doctype;
		doc.import_type = import_type;
		frm.refresh(name);
		_after_refresh(frm);
	};

	const boot_existing = () => {
		frappe.model.with_doc("Data Import", data_import, (name, r) => {
			if (r && r["403"]) {
				dialog.hide();
				frappe.show_alert({ message: __("Not permitted"), indicator: "red" });
				return;
			}
			frm.refresh(data_import);
			_after_refresh(frm);
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
		if (frm.__di_poll_timer) clearInterval(frm.__di_poll_timer);
		try {
			frm._data_import_wizard?.unmount?.();
		} catch (e) {
			// ignore
		}
		removeEventListener("beforeunload", frm.beforeUnloadListener, { capture: true });
		if (window.cur_frm === frm) window.cur_frm = null;
	});

	return { dialog, frm };
}

function _after_refresh(frm) {
	// The wizard sizes its card from the viewport (window.innerHeight). Inside a dialog
	// we want it to fill the dialog body instead. Nudge it once layout settles.
	if (frm.on_import_complete_watcher) return;
	frm.on_import_complete_watcher = true;

	const notify = frm.__di_notify_complete;
	if (notify) {
		// Poll instead of threading a callback through the controller. Clear on hide: a hidden
		// dialog keeps its wrapper in the DOM, so the contains() check alone never stops it.
		frm.__di_poll_timer = setInterval(() => {
			if (!document.body.contains(frm.wrapper)) {
				clearInterval(frm.__di_poll_timer);
				return;
			}
			notify();
		}, 1500);
	}
}
