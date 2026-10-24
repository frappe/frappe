// Copyright (c) 2026, Frappe Technologies and contributors
// License: MIT. See LICENSE

frappe.ui.form.on("Flow Knowledge Source", {
	refresh(frm) {
		apply_file_restrictions(frm);

		if (frm.is_new()) {
			return;
		}

		frm.__chunking_baseline = {
			chunk_size: frm.doc.chunk_size,
			chunk_overlap: frm.doc.chunk_overlap,
		};

		frm.add_custom_button(__("Resync"), async () => {
			await frm.call("resync", { rebuild: 0 });
			frappe.show_alert({ message: __("Resync started"), indicator: "blue" });
			frm.reload_doc();
		});

		if (frm.doc.source_type === "DocType") {
			frm.add_custom_button(__("Reconcile"), async () => {
				await frm.call("reconcile");
				frappe.show_alert({ message: __("Reconcile started"), indicator: "blue" });
			});
		}
	},

	after_save(frm) {
		const baseline = frm.__chunking_baseline;
		if (!baseline || !frm.doc.chunk_count) {
			return;
		}
		const changed =
			baseline.chunk_size !== frm.doc.chunk_size ||
			baseline.chunk_overlap !== frm.doc.chunk_overlap;
		if (!changed) {
			return;
		}
		frm.__chunking_baseline = {
			chunk_size: frm.doc.chunk_size,
			chunk_overlap: frm.doc.chunk_overlap,
		};
		frappe.confirm(
			__(
				"Chunk settings changed. The {0} existing chunks for this source will be deleted and rebuilt with the new settings. Re-process now?",
				[frm.doc.chunk_count]
			),
			() => {
				frm.call("resync", { rebuild: 1 }).then(() => {
					frappe.show_alert({ message: __("Re-ingestion started"), indicator: "blue" });
					frm.reload_doc();
				});
			}
		);
	},

	source_type(frm) {
		apply_file_restrictions(frm);
	},
});

// Cap the File picker to the formats the ingest pipeline can actually extract.
// Types come from frappe.boot
function apply_file_restrictions(frm) {
	if (frm.doc.source_type !== "File") {
		return;
	}
	const types = (frappe.boot.flow_supported_file_types || []).map((ext) => `.${ext}`);
	frm.fields_dict.file.df.options = {
		restrictions: { allowed_file_types: types },
	};
}
