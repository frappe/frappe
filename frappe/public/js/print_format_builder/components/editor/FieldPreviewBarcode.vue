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
import { ref, computed, watch, inject } from "vue";
import { is_qr_barcode_options } from "../../utils";

const props = defineProps(["df"]);
const store = inject("$store");
const preview_doc = computed(() => store.preview_doc.value);

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

let barcode_raw_value = computed(() => {
	if (props.df.fieldtype !== "Barcode") return null;
	if (!props.df.custom) {
		return preview_doc.value?.[props.df.fieldname] ?? null;
	}
	if (props.df.barcode_field) {
		return preview_doc.value?.[props.df.barcode_field] ?? null;
	}
	return props.df.barcode_value || null;
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
