export const WIZARD_STEPS = [
	{
		id: "config",
		label: __("Config"),
		icon: "settings",
		vue: true,
	},
	{
		id: "preview",
		label: __("Preview"),
		icon: "table-2",
		vue: false,
		sections: ["section_import_tree_preview", "section_import_preview"],
	},
	{
		id: "fix_issues",
		label: __("Fix issues"),
		icon: "list-todo",
		vue: false,
		sections: ["import_warnings_section", "value_mappings_section", "skipped_rows_section"],
	},
	{
		id: "import",
		label: __("Import"),
		icon: "flag",
		vue: false,
		fields: ["import_log_heading", "show_failed_logs", "import_log_preview"],
	},
];

export function get_wizard_initial_step(frm) {
	const doc = frm.doc;
	if (!doc) return 0;
	if (doc.status && doc.status !== "Pending") return 3;
	if (frm.has_import_file?.()) {
		let has_template_warnings = false;
		try {
			has_template_warnings = (JSON.parse(doc.template_warnings || "[]") || []).length > 0;
		} catch (_e) {
			has_template_warnings = false;
		}

		const has_fix_issue_state =
			(doc.skipped_rows || []).length > 0 ||
			(doc.value_mappings || []).length > 0 ||
			has_template_warnings;

		if (has_fix_issue_state) return 2;
		return 1;
	}
	return 0;
}

/** Preview / Fix Issues steps need an async fetch before their panels can render. */
export function wizard_step_needs_preview_bootstrap(frm, step) {
	if (!frm.has_import_file?.()) return false;
	if (step !== 1 && step !== 2) return false;
	if (frm._import_preview_loading || frm._import_preview_promise) return true;
	const source_key = [
		frm.doc.import_file || "",
		frm.doc.google_sheets_url || "",
		cint(frm.doc.use_csv_sniffer),
		cint(frm.doc.custom_delimiters),
		frm.doc.delimiter_options || "",
	].join("|");
	return !(frm._import_preview_ready && frm._import_preview_source_key === source_key);
}

export function has_import_started(frm) {
	const status = frm.doc?.status;
	return Boolean(frm.import_in_progress || (status && status !== "Pending"));
}

export function can_go_to_wizard_step(frm, step, current_step) {
	if (step <= current_step) return true;
	if (step === 1) {
		return (
			Boolean(frm.doc.reference_doctype && frm.doc.import_type) &&
			!frm.doc.__islocal &&
			frm.has_import_file?.()
		);
	}
	if (step === 2) {
		return !frm.doc.__islocal && frm.has_import_file?.();
	}
	if (step === 3) {
		return !frm.doc.__islocal && frm.has_import_file?.() && has_import_started(frm);
	}
	return false;
}

/** True when the import target DocType is a nested-set tree (e.g. Item Group). */
export function is_tree_reference_doctype(frm) {
	const doctype = frm.doc?.reference_doctype;
	if (!doctype) return false;
	return Boolean(frappe.get_meta(doctype)?.is_tree);
}

/** Tree preview tabs when the target is a tree DocType and preview payload is available. */
export function has_tree_import_preview(frm, preview_data = null) {
	if (!is_tree_reference_doctype(frm)) return false;
	const data =
		preview_data ||
		frm._import_preview_data ||
		frm.import_preview?.preview_data ||
		frm.import_tree_preview?.preview_data;
	return Boolean(data?.tree_preview);
}
