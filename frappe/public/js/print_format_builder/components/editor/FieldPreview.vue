<template>
	<!-- Handle HTML fields: render Jinja2 server-side if needed -->
	<span v-if="template_render_failed" class="text-muted">{{
		__("Couldn't render this template for the previewed document")
	}}</span>
	<div
		v-else-if="df.fieldtype == 'HTML' && df.html"
		v-html="strip_unsafe_html(rendered_html ?? df.html)"
	></div>
	<!-- Typst can't render in the HTML canvas — show the markup, the PDF preview shows the output -->
	<pre v-else-if="df.fieldtype == 'Typst'" class="typst-block-source">{{
		df.typst || __("Empty Typst block")
	}}</pre>
	<!-- Spacer/Divider: the root element itself is the rendered output -->
	<i v-else-if="df.fieldtype == 'Spacer' || df.fieldtype == 'Divider'" v-show="false"></i>
	<template v-else-if="df.fieldtype == 'Image'">
		<img
			v-if="df.image_url || preview_doc[df.fieldname]"
			:src="df.image_url || preview_doc[df.fieldname]"
			:style="{ maxWidth: '100%', ...(df.width ? { width: df.width } : {}) }"
			:alt="df.label || ''"
		/>
		<span v-else class="text-muted">{{ __("No image — set one in the panel") }}</span>
	</template>
	<FieldPreviewBarcode v-else-if="df.fieldtype == 'Barcode'" :df="df" />
	<div
		v-else-if="df.fieldtype == 'Field Template'"
		v-html="strip_unsafe_html(rendered_template || '')"
	></div>
	<!-- Table MultiSelect field: render as a comma-separated value list -->
	<template v-else-if="df.fieldtype == 'Table MultiSelect'">
		<div
			v-if="df.label && df.show_label !== 'hide'"
			class="label"
			:class="{ 'label--no-colon': df.hide_colon }"
			:style="label_text_style(df)"
		>
			{{ df.label }}
		</div>
		<div
			class="value"
			:class="{ 'text-muted': !(preview_doc[df.fieldname] || []).length }"
			:style="value_text_style(df)"
		>
			{{ multiselect_display(df) }}
		</div>
	</template>
	<FieldPreviewTable v-else-if="df.fieldtype == 'Table'" :df="df" />
	<FieldPreviewRepeater v-else-if="df.fieldtype == 'Repeater'" :df="df" />
	<div
		v-else-if="df.fieldtype == 'Static Text'"
		class="value"
		:class="{ 'text-muted': !df.text }"
		:style="static_text_style"
	>
		{{ df.text || __("Empty text") }}
	</div>
	<FieldPreviewLinked v-else-if="df.fieldtype == 'Linked Field'" :df="df" />
	<template v-else>
		<div
			v-if="df.label && df.show_label !== 'hide'"
			class="label"
			:class="{ 'label--no-colon': df.hide_colon }"
			:style="label_text_style(df)"
		>
			{{ df.label }}
		</div>
		<div class="value" :class="{ 'text-muted': !preview_value }" :style="value_text_style(df)">
			<img
				v-if="df.fieldtype == 'Attach Image' && preview_doc[df.fieldname]"
				:style="{ maxWidth: '100%', width: df.width || '100%' }"
				:src="preview_doc[df.fieldname]"
				:alt="df.label || df.fieldname"
			/>
			<a
				v-else-if="df.fieldtype == 'Attach' && preview_doc[df.fieldname]"
				:href="preview_doc[df.fieldname]"
				@click.prevent
				>{{ String(preview_doc[df.fieldname]).split("/").pop() }}</a
			>
			<template v-else-if="df.fieldtype == 'Color' && preview_doc[df.fieldname]">
				<div
					class="color-square"
					:style="{ backgroundColor: preview_doc[df.fieldname] }"
				></div>
				{{ preview_doc[df.fieldname] }}
			</template>
			<!-- Mirrors the star SVG of templates/print_format/macros/Rating.html -->
			<template v-else-if="df.fieldtype == 'Rating' && preview_doc[df.fieldname]">
				<svg
					v-for="i in rating_stars.total"
					:key="i"
					class="rating-star"
					:class="{ active: i <= rating_stars.filled }"
					viewBox="0 0 24 24"
					fill="none"
					xmlns="http://www.w3.org/2000/svg"
				>
					<path
						:fill="i <= rating_stars.filled ? '#f6c35e' : '#dce0e3'"
						:stroke="i <= rating_stars.filled ? '#f6c35e' : '#dce0e3'"
						d="M11.5516 2.90849C11.735 2.53687 12.265 2.53687 12.4484 2.90849L14.8226 7.71919C14.8954 7.86677 15.0362 7.96905 15.1991 7.99271L20.508 8.76415C20.9181 8.82374 21.0818 9.32772 20.7851 9.61699L16.9435 13.3616C16.8257 13.4765 16.7719 13.642 16.7997 13.8042L17.7066 19.0916C17.7766 19.5001 17.3479 19.8116 16.9811 19.6187L12.2327 17.1223C12.087 17.0457 11.913 17.0457 11.7673 17.1223L7.01888 19.6187C6.65207 19.8116 6.22335 19.5001 6.29341 19.0916L7.20028 13.8042C7.2281 13.642 7.17433 13.4765 7.05648 13.3616L3.21491 9.61699C2.91815 9.32772 3.08191 8.82374 3.49202 8.76415L8.80094 7.99271C8.9638 7.96905 9.10458 7.86677 9.17741 7.71919L11.5516 2.90849Z"
					/>
				</svg>
			</template>
			<span v-else-if="preview_value_html" v-html="preview_value_html"></span>
			<span v-else>{{ preview_value || (df.show_empty ? "" : "—") }}</span>
		</div>
	</template>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue";
import FieldPreviewBarcode from "./FieldPreviewBarcode.vue";
import FieldPreviewLinked from "./FieldPreviewLinked.vue";
import FieldPreviewRepeater from "./FieldPreviewRepeater.vue";
import FieldPreviewTable from "./FieldPreviewTable.vue";
import { render_jinja_html, strip_unsafe_html } from "../../utils";
import { useFieldFormat } from "../../composables/useFieldFormat";
import { useFieldStyles } from "./useFieldRoot";

const props = defineProps(["df"]);
const store = inject("$store");
const preview_doc = computed(() => store.preview_doc.value);
const { static_text_style } = useFieldStyles(props);
const { preview_value, preview_value_html, rating_stars, multiselect_display } = useFieldFormat(
	props,
	store,
	preview_doc
);

const label_text_style = (df) => (df.label_color ? { color: df.label_color } : {});
const value_text_style = (df) => (df.value_color ? { color: df.value_color } : {});

const rendered_html = ref(null);
const rendered_template = ref(null);
const template_render_failed = ref(false);
let html_seq = 0;
let template_seq = 0;

watch(
	[preview_doc, () => props.df.html],
	async ([doc]) => {
		const html = props.df.html;
		const seq = ++html_seq;
		if (!doc || !html || props.df.fieldtype !== "HTML") {
			rendered_html.value = null;
			template_render_failed.value = false;
			return;
		}
		const rendered = await render_jinja_html(
			html,
			store.meta.value?.name,
			store.preview_doc_name.value
		);
		if (seq !== html_seq) return;
		rendered_html.value = rendered;
		template_render_failed.value = rendered === null;
	},
	{ immediate: true }
);

watch(
	[preview_doc, () => props.df.field_template],
	async ([doc]) => {
		const seq = ++template_seq;
		if (!doc || props.df.fieldtype !== "Field Template" || !props.df.field_template) {
			rendered_template.value = null;
			template_render_failed.value = false;
			return;
		}
		try {
			const tmpl = await frappe.db.get_value(
				"Print Format Field Template",
				props.df.field_template,
				"template"
			);
			const rendered = await render_jinja_html(
				tmpl?.message?.template || "",
				store.meta.value?.name,
				store.preview_doc_name.value
			);
			if (seq !== template_seq) return;
			rendered_template.value = rendered;
			template_render_failed.value = rendered === null;
		} catch {
			if (seq !== template_seq) return;
			rendered_template.value = null;
			template_render_failed.value = true;
		}
	},
	{ immediate: true }
);
</script>
