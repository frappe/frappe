<template>
	<div class="h-100">
		<div class="row">
			<div class="col">
				<div class="preview-control" ref="doc_select_ref"></div>
			</div>
			<div class="col">
				<div class="preview-control" ref="preview_type_ref"></div>
			</div>
			<div class="col d-flex">
				<a
					v-if="url"
					class="btn btn-default btn-sm btn-new-tab"
					target="_blank"
					:href="url"
				>
					{{ __("Open in a new tab") }}
				</a>
				<button
					v-if="url"
					class="ml-3 btn btn-default btn-sm btn-new-tab"
					@click="refresh"
				>
					{{ __("Refresh") }}
				</button>
			</div>
		</div>
		<div v-if="url && !preview_loaded">Generating preview...</div>
		<iframe
			ref="iframe"
			:src="url"
			v-if="url"
			v-show="preview_loaded"
			class="preview-iframe"
			@load="preview_loaded = true"
		></iframe>
	</div>
</template>

<script setup>
import { useStore } from "./store";
import { ref, computed, onMounted } from "vue";

// mixin
let { print_format, store } = useStore();

// variables
let type = ref("PDF");
let docname = ref(null);
let preview_loaded = ref(false);
let iframe = ref(null);
let doc_select_ref = ref(null);
let preview_type_ref = ref(null);
let doc_select = ref(null);
let preview_type = ref(null);

// methods
function refresh() {
	iframe.value?.contentWindow.location.reload();
}
function get_default_docname() {
	return frappe.db.get_list(doctype.value, { limit: 1 }).then((doc) => {
		return doc.length > 0 ? doc[0].name : null;
	});
}
// computed
let doctype = computed(() => {
	return print_format.value.doc_type;
});
let url = computed(() => {
	if (!docname.value) return null;
	let params = new URLSearchParams();
	params.append("doctype", doctype.value);
	params.append("name", docname.value);
	params.append("print_format", print_format.value.name);

	if (store.value.letterhead) {
		params.append("letterhead", store.value.letterhead.name);
	}
	let _url =
		type.value == "PDF" ? `/api/method/frappe.utils.weasyprint.download_pdf` : "/printpreview";
	return `${_url}?${params.toString()}`;
});

// mounted
onMounted(() => {
	doc_select.value = frappe.ui.form.make_control({
		parent: doc_select_ref.value,
		df: {
			label: __("Select {0}", [__(doctype.value)]),
			fieldname: "docname",
			fieldtype: "Link",
			options: doctype.value,
			change: () => {
				docname.value = doc_select.value.get_value();
			},
		},
		render_input: true,
	});
	preview_type.value = frappe.ui.form.make_control({
		parent: preview_type_ref.value,
		df: {
			label: __("Preview type"),
			fieldname: "docname",
			fieldtype: "Select",
			options: ["PDF", "HTML"],
			change: () => {
				type.value = preview_type.value.get_value();
			},
		},
		render_input: true,
	});
	preview_type.value.set_value(type.value);
	get_default_docname().then((doc_name) => {
		doc_name && doc_select.value.set_value(doc_name);
	});
});
</script>

<style scoped>
.preview-iframe {
	width: 100%;
	height: 96%;
	border: none;
	border-radius: var(--border-radius);
}
.btn-new-tab {
	margin-top: auto;
	margin-bottom: 1.2rem;
}
.preview-control :deep(.form-control) {
	background: var(--control-bg-on-gray);
}
</style>
