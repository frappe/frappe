<template>
	<img v-if="format == 'QR' && qr_src" :src="qr_src" :style="{ width: df.width || '35mm' }" />
	<div
		v-else-if="barcode_svg"
		class="pf-barcode-svg"
		:style="df.width ? { width: df.width } : {}"
		v-html="barcode_svg"
	></div>
	<span v-else-if="barcode_raw_value && format !== 'QR'" class="text-muted">{{
		__("Invalid value for {0}", [format || "CODE128"])
	}}</span>
	<span v-else-if="!df.custom" class="text-muted">{{ __("No value to encode") }}</span>
	<span v-else class="text-muted">{{ __("No barcode value — set one in the panel") }}</span>
</template>

<script setup>
import { ref, computed, watch, inject } from "vue";
import JsBarcode from "jsbarcode";
import { sanitize_html, is_qr_barcode_options } from "../../utils";

const props = defineProps(["df"]);
const store = inject("$store");
const preview_doc = computed(() => store.preview_doc.value);

let qr_src = ref(null);

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

let barcode_svg = computed(() => {
	const value = barcode_raw_value.value;
	if (!value || format.value === "QR") return null;
	const str = String(value);
	if (str.startsWith("<svg")) return sanitize_html(str);
	const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
	try {
		JsBarcode(svg, str, {
			format: format.value || "CODE128",
			displayValue: props.df.show_text !== false,
			height: 40,
			margin: 0,
		});
		svg.setAttribute("width", "100%");
		return svg.outerHTML;
	} catch {
		return null;
	}
});

watch(
	[barcode_raw_value, format],
	frappe.utils.debounce(async ([value, format]) => {
		if (format !== "QR" || !value) {
			qr_src.value = null;
			return;
		}
		try {
			const r = await frappe.call("frappe.utils.print_format_generator.get_qr_code", {
				value: String(value),
			});
			qr_src.value = r.message || null;
		} catch {
			qr_src.value = null;
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
