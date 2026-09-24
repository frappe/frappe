import { nextTick, ref } from "vue";

const VERSION_FIELDS = [
	"font",
	"font_size",
	"page_number",
	"show_label_colon",
	"margin_top",
	"margin_bottom",
	"margin_left",
	"margin_right",
	"label_color",
	"value_color",
	"css",
	"pdf_generator",
];

export function useVersions({
	name,
	print_format,
	dirty,
	viewing_version,
	call_format,
	after_autosave,
	replace_from_server,
	get_preview_format_doc,
	adopt_layout,
	pause_history,
	clear_selection,
}) {
	const versions = ref([]);
	const show_history = ref(false);
	let edit_state = null;

	function load_versions() {
		return call_format("get_versions").then((r) => (versions.value = r.message || []));
	}
	function save_version(label) {
		return after_autosave()
			.then(() =>
				call_format("save_version", {
					label,
					data: get_preview_format_doc(),
					modified: print_format.value.modified,
				})
			)
			.then(() => load_versions())
			.then(() => frappe.show_alert({ message: __("Version saved"), indicator: "green" }));
	}
	function delete_version(version) {
		return call_format("delete_version", { version })
			.then(() => {
				if (viewing_version.value?.name === version) exit_version();
				return load_versions();
			})
			.then(() => frappe.show_alert({ message: __("Version deleted"), indicator: "green" }));
	}
	function restore_version(version) {
		forget_version();
		return replace_from_server(
			__("Restoring…"),
			() =>
				call_format("restore_version", { version, modified: print_format.value.modified }),
			__("Version restored")
		);
	}
	function show_version_fields(fields) {
		adopt_layout(frappe.utils.parse_json(fields.format_data));
		VERSION_FIELDS.forEach((f) => (print_format.value[f] = fields[f]));
		clear_selection();
		nextTick(() => (dirty.value = false));
	}
	function view_version(version) {
		const fields_ready = version.published
			? frappe.db.get_doc("Print Format", name)
			: call_format("get_version_fields", { version: version.name }).then((r) => r.message);
		return fields_ready.then((fields) => {
			if (!edit_state) {
				edit_state = get_preview_format_doc();
				pause_history(true);
			}
			viewing_version.value = version;
			show_version_fields(fields);
		});
	}
	function forget_version() {
		edit_state = null;
		viewing_version.value = null;
		pause_history(false);
	}
	function exit_version() {
		if (!edit_state) return;
		show_version_fields(edit_state);
		forget_version();
	}
	function toggle_history() {
		if (show_history.value) close_history();
		else show_history.value = true;
	}
	function close_history() {
		exit_version();
		show_history.value = false;
	}
	function refresh_if_open() {
		return show_history.value && load_versions().catch(() => {});
	}

	return {
		versions,
		show_history,
		load_versions,
		save_version,
		delete_version,
		restore_version,
		view_version,
		forget_version,
		exit_version,
		toggle_history,
		close_history,
		refresh_if_open,
	};
}
