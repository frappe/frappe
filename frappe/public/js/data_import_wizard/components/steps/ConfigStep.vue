<script setup>
import { ref, watch, onMounted, onBeforeUnmount, computed, inject, nextTick } from "vue";
import FrmField from "../FrmField.vue";
import UploadSourceTabs from "../UploadSourceTabs.vue";
import { use_field_visible } from "../../composables/use_field_visibility.js";

const props = defineProps({
	docname: { type: String, required: true },
});

const frm = inject("frm");

const show_submit_after_import = ref(false);

const docname_signal = () => props.docname;

const show_download_template = use_field_visible(frm, "download_template", [docname_signal]);
const show_google_sheets = use_field_visible(frm, "google_sheets_url", [docname_signal]);
const show_refresh_sheet = use_field_visible(frm, "refresh_google_sheet", [docname_signal]);

const show_custom_delimiters = use_field_visible(frm, "custom_delimiters", [docname_signal]);
const show_delimiter_options = use_field_visible(frm, "delimiter_options", [docname_signal]);
const show_csv_sniffer = use_field_visible(frm, "use_csv_sniffer", [docname_signal]);
const has_google_sheets_url = ref(Boolean(frm.doc.google_sheets_url));
const form_is_dirty = ref(Boolean(frm.is_dirty?.()));
const show_upload_source_tabs = computed(
	() => show_google_sheets.value && !(has_google_sheets_url.value && !form_is_dirty.value)
);

const upload_source = ref("file_upload");
const google_sheets_field_ref = ref(null);

function sync_google_sheet_url_state() {
	has_google_sheets_url.value = Boolean(frm.doc.google_sheets_url);
	form_is_dirty.value = Boolean(frm.is_dirty?.());
}

function refresh_submit_after_import() {
	const doctype = frm.doc.reference_doctype;
	if (!doctype) {
		show_submit_after_import.value = false;
		return;
	}
	frappe.model.with_doctype(doctype, () => {
		show_submit_after_import.value = !!frappe.get_meta(doctype)?.is_submittable;
	});
}

onMounted(() => {
	refresh_submit_after_import();
	sync_upload_source();
	sync_google_sheet_url_state();
	$(frm.wrapper).on(
		"dirty.diw_config_step form-refresh.diw_config_step diw-import-preview-state.diw_config_step",
		sync_google_sheet_url_state
	);
	if (upload_source.value === "google_sheet" && show_google_sheets.value) {
		focus_google_sheets_url();
	}
});

onBeforeUnmount(() => {
	$(frm.wrapper).off(
		"dirty.diw_config_step form-refresh.diw_config_step diw-import-preview-state.diw_config_step",
		sync_google_sheet_url_state
	);
});

function sync_upload_source() {
	const has_google_sheet_url = Boolean(frm.doc.google_sheets_url);
	upload_source.value = has_google_sheet_url ? "google_sheet" : "file_upload";
}

/** Focus the Google Sheets URL field after the tab pane mounts. */
function focus_google_sheets_url() {
	nextTick(() => {
		requestAnimationFrame(() => {
			google_sheets_field_ref.value?.focus?.();
		});
	});
}

watch(
	() => frm.doc.reference_doctype,
	() => refresh_submit_after_import()
);

watch(
	() => props.docname,
	() => sync_upload_source()
);

watch(
	() => frm.doc.google_sheets_url,
	(value) => {
		has_google_sheets_url.value = Boolean(value);
		form_is_dirty.value = Boolean(frm.is_dirty?.());
		if (value && upload_source.value !== "google_sheet") {
			upload_source.value = "google_sheet";
		}
	}
);

watch(upload_source, (source) => {
	if (source === "google_sheet" && show_google_sheets.value) {
		focus_google_sheets_url();
	}
});

watch(show_google_sheets, (visible) => {
	if (!visible && upload_source.value === "google_sheet") {
		upload_source.value = "file_upload";
	}
});
</script>

<template>
	<div class="diw-config-step">
		<div class="form-section card-section diw-config-section">
			<div class="section-head">
				<span class="diw-section-head-title">{{ __("Import settings") }}</span>
			</div>
			<div class="section-body diw-config-grid">
				<div class="form-column col-sm-6 diw-config-main">
					<form @submit.prevent>
						<FrmField fieldname="reference_doctype" />
						<FrmField fieldname="import_type" />
					</form>
				</div>
				<div class="form-column col-sm-6 diw-config-options">
					<form @submit.prevent>
						<FrmField fieldname="mute_emails" />
						<FrmField
							v-if="show_submit_after_import"
							fieldname="submit_after_import"
						/>
						<FrmField v-if="show_custom_delimiters" fieldname="custom_delimiters" />
						<FrmField v-if="show_delimiter_options" fieldname="delimiter_options" />
						<FrmField v-if="show_csv_sniffer" fieldname="use_csv_sniffer" />
					</form>
				</div>
			</div>
		</div>

		<div class="diw-upload-section">
			<div class="diw-upload-header">
				<span class="diw-section-head-title">{{ __("Upload file") }}</span>
				<span v-if="show_download_template" class="diw-upload-header-action">
					<FrmField fieldname="download_template" />
				</span>
			</div>

			<UploadSourceTabs v-if="show_upload_source_tabs" v-model="upload_source" />

			<div
				v-if="upload_source === 'file_upload'"
				class="diw-upload-pane diw-upload-pane-file"
			>
				<FrmField
					:key="`import_file-${props.docname}`"
					fieldname="import_file"
					:docname="props.docname"
				/>
			</div>
			<div
				v-if="show_google_sheets && upload_source === 'google_sheet'"
				class="diw-upload-pane diw-upload-pane-sheet"
			>
				<FrmField
					ref="google_sheets_field_ref"
					:key="`google_sheets_url-${props.docname}`"
					fieldname="google_sheets_url"
				/>
			</div>
			<div
				v-if="show_refresh_sheet && upload_source === 'google_sheet'"
				class="diw-upload-pane"
			>
				<FrmField fieldname="refresh_google_sheet" />
			</div>
		</div>
	</div>
</template>
