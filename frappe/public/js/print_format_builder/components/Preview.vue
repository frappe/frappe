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
				<a v-if="url" class="es-button btn-new-tab" target="_blank" :href="url">
					{{ __("Open in a new tab") }}
				</a>
				<button v-if="url" class="ml-3 es-button btn-new-tab" @click="refresh">
					{{ __("Refresh") }}
				</button>
			</div>
		</div>
		<div v-if="docname && !preview_loaded">{{ __("Generating preview...") }}</div>
		<iframe
			ref="iframe"
			:src="type === 'PDF' ? url : undefined"
			v-show="docname && preview_loaded"
			class="preview-iframe"
			@load="type === 'PDF' && (preview_loaded = true)"
		></iframe>
	</div>
</template>

<script setup>
import { useStore } from "../stores";
import { ref, computed, onMounted, onActivated } from "vue";

// mixin
let { print_format, store } = useStore();

// variables
let type = ref("HTML");
let docname = ref(null);
let preview_loaded = ref(false);
let iframe = ref(null);
let doc_select_ref = ref(null);
let preview_type_ref = ref(null);
let doc_select = ref(null);
let preview_type = ref(null);
let render_seq = 0;

// methods
function write_iframe(html) {
	let cd = iframe.value?.contentDocument;
	if (!cd) return;
	cd.open();
	cd.write(html);
	cd.close();
}
function render() {
	if (!docname.value) return;
	if (type.value === "PDF") return;
	preview_loaded.value = false;
	let seq = ++render_seq;
	let params = {
		print_format: store.value.get_preview_format_doc(),
		doctype: doctype.value,
		name: docname.value,
	};
	if (store.value.letterhead) {
		params.letterhead = store.value.letterhead.name;
	}
	return frappe
		.call("frappe.utils.print_format_generator.render_builder_preview", params)
		.then((r) => {
			if (seq !== render_seq) return;
			write_iframe(r.message || "");
			preview_loaded.value = true;
		})
		.catch(() => {
			if (seq !== render_seq) return;
			write_iframe(`<p style="padding:1rem">${__("Could not generate preview.")}</p>`);
			preview_loaded.value = true;
		});
}
function refresh() {
	if (type.value === "PDF") {
		iframe.value?.contentWindow.location.reload();
	} else {
		render();
	}
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
		type.value == "PDF"
			? `/api/method/frappe.utils.print_format_generator.download_pdf`
			: "/printpreview";
	return `${_url}?${params.toString()}`;
});

onActivated(render);

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
				// keep the editor's preview selection in sync with the preview
				store.value.load_preview_doc(docname.value || null);
				render();
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
			options: ["HTML", "PDF"],
			change: () => {
				type.value = preview_type.value.get_value();
				render();
			},
		},
		render_input: true,
	});
	preview_type.value.set_value(type.value);
	// Prefer the document already chosen while editing; only fall back to a
	// default when nothing has been selected yet. `store` is ref(inject("$store")),
	// so `store.value` is a reactive proxy that unwraps preview_doc_name to a string.
	const selected = store.value.preview_doc_name;
	if (selected) {
		doc_select.value.set_value(selected);
	} else {
		get_default_docname().then((doc_name) => {
			doc_name && doc_select.value.set_value(doc_name);
		});
	}
});
</script>

<style scoped>
.preview-iframe {
	width: 100%;
	height: 96%;
	border: none;
	border-radius: var(--radius);
}
.btn-new-tab {
	margin-top: auto;
	margin-bottom: 1.2rem;
}
.preview-control :deep(.form-control) {
	background: var(--control-bg-on-gray);
}
</style>
