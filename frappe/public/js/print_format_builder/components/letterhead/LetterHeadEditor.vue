<template>
	<div
		class="letterhead"
		:class="{ 'letterhead--selected': store.selected_letterhead.value }"
		@click.stop="select_letterhead"
	>
		<div v-if="letterhead">
			<!-- In preview mode with a doc loaded: show rendered output -->
			<div v-if="preview_doc" v-html="rendered_content ?? letterhead.content"></div>
			<!-- Edit mode: show raw content as-is -->
			<div v-else v-html="letterhead.content"></div>
		</div>
		<div v-else class="letterhead-empty">
			<span v-html="frappe.utils.icon('image', 'sm')"></span>
			<span>{{ __("No Letter Head — click to add") }}</span>
		</div>
	</div>
</template>

<script setup>
import { useStore } from "../../stores";
import { get_image_dimensions } from "../../utils";
import { ref, watch, onMounted, inject, computed } from "vue";

let { letterhead, store, layout } = useStore();
let raw_store = inject("$store");

let aspect_ratio = ref(null);
let range_input_field = ref(null);
let rendered_content = ref(null);
let render_pending = ref(false);

let preview_doc = computed(() => raw_store.preview_doc.value);

function select_letterhead() {
	raw_store.selected_letterhead.value = true;
	raw_store.selected_lh_footer.value = false;
	raw_store.selected_field.value = null;
	raw_store.selected_section.value = null;
}

function set_letterhead(_letterhead) {
	store.value.change_letterhead(_letterhead);
}

function needs_server_render(content) {
	return content && (content.includes("{{") || content.includes("{%"));
}

async function refresh_rendered_content() {
	const doc = preview_doc.value;
	const content = letterhead.value?.content;

	if (!doc || !content) {
		rendered_content.value = null;
		return;
	}

	// Plain HTML (image-based letterheads) — no server round-trip needed
	if (!needs_server_render(content)) {
		rendered_content.value = content;
		return;
	}

	if (render_pending.value) return;
	render_pending.value = true;
	try {
		const r = await frappe.call("frappe.utils.print_format_generator.render_jinja_template", {
			template: content,
			doctype: raw_store.meta.value.name,
			docname: raw_store.preview_doc_name.value,
		});
		rendered_content.value = r.message ?? content;
	} catch {
		rendered_content.value = content;
	} finally {
		render_pending.value = false;
	}
}

// Re-render when preview doc or letterhead content changes
watch([preview_doc, () => letterhead.value?.content], refresh_rendered_content, {
	immediate: true,
});

onMounted(() => {
	if (!letterhead.value && !layout.value?.letter_head) {
		const lh_name = frappe.boot.sysdefaults.letter_head;
		if (lh_name) set_letterhead(lh_name);
	}
});

// Maintain aspect ratio when slider moves
watch(
	() => (letterhead.value ? letterhead.value[range_input_field.value] : null),
	() => {
		if (aspect_ratio.value === null) return;
		let update_field =
			range_input_field.value == "image_width" ? "image_height" : "image_width";
		letterhead.value[update_field] =
			update_field == "image_width"
				? aspect_ratio.value * letterhead.value.image_height
				: letterhead.value.image_width / aspect_ratio.value;
	}
);

// Initialize slider state when letterhead image is set/replaced
watch(
	letterhead,
	(lh) => {
		if (lh?.image) {
			get_image_dimensions(lh.image).then(({ width, height }) => {
				aspect_ratio.value = width / height;
				range_input_field.value = aspect_ratio.value > 1 ? "image_width" : "image_height";
			});
		}
	},
	{ immediate: true }
);

// Rebuild content HTML whenever image dimensions or alignment change
watch(
	letterhead,
	() => {
		if (!letterhead.value) return;
		if (letterhead.value.image_width && letterhead.value.image_height) {
			let dimension =
				letterhead.value.image_width > letterhead.value.image_height ? "width" : "height";
			let dimension_value = letterhead.value["image_" + dimension];
			letterhead.value.content = `
			<div style="text-align: ${letterhead.value.align.toLowerCase()};">
				<img
					src="${letterhead.value.image}"
					alt="${letterhead.value.name}"
					${dimension}="${dimension_value}"
					style="${dimension}: ${dimension_value}px;">
			</div>
		`;
		}
	},
	{ deep: true },
	{ immediate: true }
);

// Expose for inspector
defineExpose({ aspect_ratio, range_input_field });
</script>

<style scoped>
.letterhead {
	position: relative;
	border: 1px solid transparent;
	border-radius: var(--border-radius);
	padding: 1rem;
	margin-bottom: 1rem;
	cursor: pointer;
	transition: border-color 0.15s;
}

.letterhead:hover {
	border-color: var(--gray-300);
}

.letterhead--selected {
	border-color: var(--primary);
}

.letterhead-empty {
	display: flex;
	align-items: center;
	gap: 6px;
	color: var(--text-muted);
	font-size: var(--text-sm);
	padding: 0.5rem 0;
}
</style>
