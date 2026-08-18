<template>
	<div class="lh-zone" :class="{ 'lh-zone--selected': is_selected }" @click.stop="select_zone">
		<div v-if="letterhead && zone_content" class="letter-head">
			<!-- Preview mode: render Jinja server-side; edit mode: show raw -->
			<span v-if="preview_doc && render_failed" class="text-muted">{{
				__("Couldn't render this letter head for the previewed document")
			}}</span>
			<div v-else-if="preview_doc" v-html="rendered_content ?? zone_content"></div>
			<div v-else v-html="zone_content"></div>
		</div>
		<div v-else-if="letterhead" class="lh-zone-empty">
			<span v-html="frappe.utils.icon('image', 'sm')"></span>
			<span>{{ empty_label }}</span>
		</div>
		<div v-else class="lh-zone-blank"></div>
	</div>
</template>

<script setup>
import { useStore } from "../../stores";
import { render_jinja_html } from "../../utils";
import { ref, watch, onMounted, inject, computed } from "vue";

const props = defineProps({
	zone: { type: String, required: true }, // 'header' | 'footer'
});

let { letterhead, store, layout } = useStore();
let raw_store = inject("$store");

// ── Field name mapping ────────────────────────────────────
const F = computed(() =>
	props.zone === "header"
		? {
				source: "source",
				content: "content",
				image: "image",
				align: "align",
				height: "image_height",
				width: "image_width",
		  }
		: {
				source: "footer_source",
				content: "footer",
				image: "footer_image",
				align: "footer_align",
				height: "footer_image_height",
				width: "footer_image_width",
		  }
);

let preview_doc = computed(() => raw_store.preview_doc.value);
let rendered_content = ref(null);
let render_failed = ref(false);
let render_pending = ref(false);

let zone_content = computed(() => letterhead.value?.[F.value.content] ?? "");
let is_selected = computed(() =>
	props.zone === "header"
		? raw_store.selected_letterhead.value
		: raw_store.selected_lh_footer.value
);
let empty_label = computed(() =>
	letterhead.value ? __("{0} is empty — click to add", [letterhead.value.name]) : ""
);

function select_zone() {
	raw_store.select_letterhead({ footer: props.zone !== "header" });
}

async function refresh_rendered_content() {
	const doc = preview_doc.value;
	const content = zone_content.value;
	if (!doc || !content) {
		rendered_content.value = null;
		render_failed.value = false;
		return;
	}
	if (render_pending.value) return;
	render_pending.value = true;
	try {
		rendered_content.value = await render_jinja_html(
			content,
			raw_store.meta.value?.name,
			raw_store.preview_doc_name.value
		);
		render_failed.value = rendered_content.value === null;
	} finally {
		render_pending.value = false;
	}
}

watch([preview_doc, zone_content], refresh_rendered_content, { immediate: true });

// ── Image-based content builder ───────────────────────────
function build_image_content() {
	if (!letterhead.value) return;
	const lh = letterhead.value;
	const f = F.value;
	if (!lh[f.image] || !lh[f.width] || !lh[f.height]) return;
	const dim = lh[f.width] > lh[f.height] ? "width" : "height";
	const dim_val = lh[f[dim]];
	lh[f.content] = `<div style="text-align:${(lh[f.align] || "Left").toLowerCase()}">
<img src="${lh[f.image]}" alt="${lh.name}" ${dim}="${dim_val}" style="${dim}:${dim_val}px">
</div>`;
}

watch(
	() => {
		if (!letterhead.value) return null;
		const f = F.value;
		return [
			letterhead.value[f.image],
			letterhead.value[f.align],
			letterhead.value[f.width],
			letterhead.value[f.height],
		];
	},
	build_image_content,
	{ deep: true }
);

onMounted(() => {
	if (props.zone === "header" && !letterhead.value && layout.value?.letter_head == null) {
		const lh_name = frappe.boot.sysdefaults.letter_head;
		if (lh_name) store.value.change_letterhead(lh_name, { keep_clean: true });
	}
});
</script>

<style scoped>
.lh-zone {
	position: relative;
	border: 1px solid transparent;
	border-radius: var(--radius);
	padding: 1rem;
	cursor: pointer;
	transition: border-color 0.15s;
}

.lh-zone--selected {
	border-color: var(--gray-400);
}

.lh-zone:hover {
	border-color: var(--gray-300);
}

.lh-zone-empty {
	display: flex;
	align-items: center;
	gap: 6px;
	color: var(--text-muted);
	font-size: var(--text-sm);
	padding: 0.5rem 0;
}

.lh-zone:has(.lh-zone-blank) {
	padding: 0.25rem;
}

.lh-zone :deep(img) {
	max-width: 100%;
	height: auto;
}
</style>
