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

	// in_form=false: an embedded/dialog form, NOT a standalone form view. This makes
	// Form.rename_notify() skip its frappe.set_route() on the first save of a new doc
	// (form.js: `if (this.meta.in_dialog || !this.in_form) return`) — otherwise saving a
	// new-* doc navigates the whole desk to the form view and tears the dialog down.
	const frm = new frappe.ui.form.Form("Data Import", $host.get(0), false);

	// Let the wizard / controller know it is embedded (so page-context tweaks below
	// and any future in-dialog branches can key off it).
	frm.in_dialog = true;
	frm._data_import_dialog = dialog;

	// Optional: notify caller when the import finishes. The controller flips status to
	// Success/Partial Success; we watch on each refresh.
	if (on_import_complete) {
		const orig_refresh = frm.cscript?.refresh;
		frm.__di_notify_complete = () => {
			if (["Success", "Partial Success"].includes(frm.doc?.status) && !frm.__di_notified) {
				frm.__di_notified = true;
				on_import_complete(frm);
			}
		};
	}

	const boot_new = () => {
		// A plain new (unsaved) doc — nothing is persisted until the wizard saves, which
		// only happens after the user attaches a file / advances. So opening the dialog and
		// closing it without attaching anything creates NO Data Import record. The first
		// save renames new-* → real name; with in_form=false above, that no longer reroutes.
		// (get_new_doc initializes frappe.model.docinfo[doctype][name], so get_docinfo is safe.)
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
	_inject_dialog_css();
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
		removeEventListener("beforeunload", frm.beforeUnloadListener, { capture: true });
		if (window.cur_frm === frm) window.cur_frm = null;
	});

	return { dialog, frm };
}

// The embedded form builds a full desk page (make_app_page) inside the dialog body —
// that page has its own head (breadcrumbs, search, page-actions) and sidebar which are
// redundant chrome in a modal. Hide them so only the wizard shows. Also constrain the
// dialog body height so the wizard's viewport-based card sizing scrolls inside the modal.
function _inject_dialog_css() {
	if (document.getElementById("data-import-dialog-css")) return;
	const css = `
		.data-import-dialog .modal-dialog { max-width: min(1200px, 94vw); }
		/* This dialog has no footer buttons, so the modal-footer (which carries the rounded
		   bottom corners) is hidden and the square-cornered modal-body becomes the bottom
		   edge. Round its bottom corners so they match the modal-content's radius. */
		.data-import-dialog .modal-body {
			padding: 0;
			max-height: 84vh;
			overflow: hidden;
			border-bottom-left-radius: var(--radius-md, 0.75rem);
			border-bottom-right-radius: var(--radius-md, 0.75rem);
		}
		.data-import-dialog .data-import-dialog-host .page-head,
		.data-import-dialog .data-import-dialog-host .layout-side-section,
		.data-import-dialog .data-import-dialog-host .form-sidebar,
		.data-import-dialog .data-import-dialog-host .page-actions { display: none !important; }
		.data-import-dialog .data-import-dialog-host .page-body,
		.data-import-dialog .data-import-dialog-host .layout-main-section-wrapper { padding: 0; }
		/* The wizard floors the card at 620px from the viewport; inside a modal that
		   overflows the dialog and forces a scroll. Cap it to the dialog body so the
		   whole card (stepper + config + footer) is visible; long step content still
		   scrolls inside .diw-step-content. !important beats the wizard's inline height. */
		.data-import-dialog .diw-card {
			height: calc(84vh - 96px) !important;
			min-height: calc(84vh - 96px) !important;
			max-height: calc(84vh - 96px) !important;
		}
	`;
	const style = document.createElement("style");
	style.id = "data-import-dialog-css";
	style.textContent = css;
	document.head.appendChild(style);
}

function _after_refresh(frm) {
	// The wizard sizes its card from the viewport (window.innerHeight). Inside a dialog
	// we want it to fill the dialog body instead. Nudge it once layout settles.
	if (frm.on_import_complete_watcher) return;
	frm.on_import_complete_watcher = true;

	const notify = frm.__di_notify_complete;
	if (notify) {
		// Cheap poll — the controller re-renders on realtime import progress; checking
		// on an interval avoids threading a callback through the whole controller.
		const timer = setInterval(() => {
			if (!document.body.contains(frm.wrapper)) {
				clearInterval(timer);
				return;
			}
			notify();
		}, 1500);
	}
}
