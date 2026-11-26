<template>
	<img
		v-if="barcode_img || barcode_src"
		class="pf-barcode-svg"
		:src="barcode_img || barcode_src"
		:style="df.width ? { width: df.width } : format == 'QR' ? { width: '35mm' } : {}"
		alt=""
	/>
	<span v-else-if="barcode_raw_value && !loading" class="text-muted">{{
		__("Invalid value for {0}", [format || "CODE128"])
	}}</span>
	<span v-else-if="!df.custom" class="text-muted">{{ __("No value to encode") }}</span>
	<span v-else class="text-muted">{{ __("No barcode value — set one in the panel") }}</span>
</template>

<script setup>
import { ref, computed, watch, watchEffect, inject } from "vue";
import { linked_target } from "../../composables/linkedValues";
import { is_qr_barcode_options, text_field_paths } from "../../utils";

const props = defineProps(["df"]);
const store = inject("$store");
const preview_doc = computed(() => store.preview_doc.value);

const paths = ref([]);
watchEffect(async (onCleanup) => {
	let stale = false;
	onCleanup(() => (stale = true));
	const value = props.df.barcode_value || "";
	const meta = store.meta.value;
	const links = (meta?.fields || []).filter(
		(f) => f.fieldtype === "Link" && f.options && value.includes(`{${f.fieldname}.`)
	);
	await Promise.all(links.map((f) => frappe.model.with_doctype(f.options)));
	if (!stale) paths.value = text_field_paths(value, meta);
});

const linked = ref({});
watchEffect(() => {
	const doc = preview_doc.value;
	for (const path of paths.value) {
		if (!path.includes(".")) continue;
		const target = linked_target({ link_path: path }, store.meta.value, doc);
		if (!target || target.key in linked.value) continue;
		linked.value[target.key] = "";
		frappe.db
			.get_value(target.doctype, target.name, target.fieldname)
			.then((r) => (linked.value[target.key] = r?.message?.[target.fieldname] ?? ""));
	}
});

let barcode_src = ref(null);
let loading = ref(true);

// a Barcode docfield whose options ask for a qr code renders as one — the
// field decides, there is no format control
let is_qr_field = computed(() => {
	if (props.df.custom) return false;
	const meta_df = (store.meta.value?.fields || []).find(
		(f) => f.fieldname === props.df.fieldname
	);
	return !!meta_df && is_qr_barcode_options(meta_df.options);
});

let format = computed(() => {
	if (props.df.custom) return props.df.barcode_format;
	return is_qr_field.value ? "QR" : null;
});

// the print encodes Python's str() of the stored value, which writes a whole float as "5.0"
function raw_text(value, meta, fieldname) {
	if (value == null) return "";
	const fieldtype = meta?.fields?.find((f) => f.fieldname === fieldname)?.fieldtype;
	const is_float = fieldtype !== "Int" && frappe.model.numeric_fieldtypes.includes(fieldtype);
	return is_float && Number.isInteger(value) ? value.toFixed(1) : String(value);
}

let barcode_raw_value = computed(() => {
	if (props.df.fieldtype !== "Barcode") return null;
	if (!props.df.custom) {
		return preview_doc.value?.[props.df.fieldname] ?? null;
	}
	const doc = preview_doc.value;
	if (props.df.barcode_field) {
		const field = props.df.barcode_field;
		return raw_text(doc?.[field], store.meta.value, field) || null;
	}
	const value = (props.df.barcode_value || "").replace(/\{([\w.]+)\}/g, (token, path) => {
		if (!paths.value.includes(path) || !doc) return token;
		if (!path.includes(".")) return raw_text(doc[path], store.meta.value, path);
		const target = linked_target({ link_path: path }, store.meta.value, doc);
		if (!target) return "";
		return raw_text(
			linked.value[target.key],
			frappe.get_meta(target.doctype),
			target.fieldname
		);
	});
	return value || null;
});

// A Barcode docfield stores its own <svg>. That markup is document data, not
// something the format author wrote, so it renders as an image rather than into
// the desk DOM: an SVG in <img> runs no script and fetches nothing external.
let barcode_img = computed(() => {
	const value = barcode_raw_value.value;
	const str = String(value || "");
	if (!str.startsWith("<svg")) return null;
	return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(str)}`;
});

watch(
	[barcode_raw_value, barcode_img, format, () => props.df.show_text],
	frappe.utils.debounce(async ([value, img, format, show_text]) => {
		barcode_src.value = null;
		if (!value || img) return;
		loading.value = true;
		try {
			const r = await frappe.call("frappe.utils.print_format_generator.get_barcode", {
				value: String(value),
				barcode_format: format || "CODE128",
				show_text: props.df.custom ? show_text ?? true : true,
			});
			barcode_src.value = r.message || null;
		} catch {
			barcode_src.value = null;
		} finally {
			loading.value = false;
		}
	}, 300),
	{ immediate: true }
);
</script>

<style scoped>
.pf-barcode-svg {
	display: inline-block;
	max-width: 100%;
}
</style>
