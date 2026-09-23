<template>
	<div class="pfb-insp-body">
		<!-- Zone label — footer only (matches original design; header has no zone label) -->
		<div v-if="zone === 'footer'" class="pfb-lh-zone-label">
			<span v-html="frappe.utils.icon('panel-bottom', 'xs')"></span>
			{{ __("Letter Head Footer") }}
		</div>

		<!-- Based on toggle + letter head actions -->
		<div class="pfb-insp-section">
			<div class="pfb-insp-section-body" style="padding-top: 10px">
				<SegmentedRow
					v-if="letterhead"
					:label="__('Based on')"
					:model-value="zone_source"
					:options="[
						{ value: 'Image', label: __('Image') },
						{ value: 'HTML', label: __('HTML') },
					]"
					@update:model-value="set_source"
				/>
			</div>
		</div>

		<!-- HTML section -->
		<InspectorSection v-if="letterhead && zone_source === 'HTML'" :label="__('HTML')">
			<div
				class="pfb-html-preview"
				v-if="letterhead[html_content_field]"
				v-html="letterhead[html_content_field]"
			></div>
			<div v-else class="pfb-insp-hint text-muted">
				{{ __("No HTML content yet.") }}
			</div>
			<button class="es-button" data-size="xs" @click="edit_html">
				<span v-html="frappe.utils.icon('pencil', 'xs')"></span>
				{{ __("Edit HTML") }}
			</button>
		</InspectorSection>

		<!-- Image section -->
		<InspectorSection v-if="letterhead && zone_source === 'Image'" :label="__('Image')">
			<!-- Alignment -->
			<SegmentedRow
				:label="__('Align')"
				:model-value="zone_align"
				:options="
					['Left', 'Center', 'Right'].map((d) => ({
						value: d,
						label: __(d),
					}))
				"
				@update:model-value="set_align"
			/>
			<SliderRow
				v-if="letterhead[image_field]"
				:label="__('Size')"
				:max="zone_size_max"
				:model-value="zone_size"
				@update:model-value="set_size"
			/>
			<!-- Image source -->
			<ImageUploadControl
				:model-value="letterhead[image_field] || ''"
				@update:model-value="set_image"
			/>
		</InspectorSection>
	</div>
</template>

<script setup>
import { computed, inject, onMounted, ref } from "vue";
import { get_image_dimensions } from "../../utils";
import { zone_fields } from "../letterhead/zone_fields";
import { open_html_editor } from "../../composables/useHtmlEditorDialog";
import SegmentedRow from "./SegmentedRow.vue";
import SliderRow from "./SliderRow.vue";
import InspectorSection from "./InspectorSection.vue";
import ImageUploadControl from "./ImageUploadControl.vue";

const props = defineProps({
	zone: { type: String, required: true },
});

const store = inject("$store");
const { letterhead } = store;

const F = computed(() => zone_fields(props.zone));
const source_field = computed(() => F.value.source);
const align_field = computed(() => F.value.align);
const image_field = computed(() => F.value.image);
const html_content_field = computed(() => F.value.content);
const width_field = computed(() => F.value.width);
const height_field = computed(() => F.value.height);

const zone_source = computed(() => letterhead.value?.[source_field.value] || "Image");
const zone_align = computed(() => letterhead.value?.[align_field.value] ?? "Left");

const aspect_ratio = ref(null);
const range_field = ref(null);

onMounted(() => {
	const img = letterhead.value?.[image_field.value];
	if (img) {
		get_image_dimensions(img)
			.then(({ width, height }) => {
				aspect_ratio.value = width / height;
				range_field.value =
					aspect_ratio.value > 1 ? width_field.value : height_field.value;
			})
			.catch(() => {});
	} else {
		range_field.value = width_field.value;
	}
});

const zone_size = computed(() => {
	const rf = range_field.value ?? width_field.value;
	return letterhead.value?.[rf] ?? (rf === width_field.value ? 200 : 80);
});

const zone_size_max = computed(() => {
	const rf = range_field.value ?? width_field.value;
	return rf === width_field.value ? 700 : 500;
});

function set_source(val) {
	if (!letterhead.value) return;
	letterhead.value[source_field.value] = val;
	letterhead.value._dirty = true;
}

function set_align(val) {
	if (!letterhead.value) return;
	letterhead.value[align_field.value] = val;
	letterhead.value._dirty = true;
}

function set_size(val) {
	if (!letterhead.value || !range_field.value) return;
	const v = parseFloat(val);
	letterhead.value[range_field.value] = v;
	if (aspect_ratio.value) {
		const is_width = range_field.value === width_field.value;
		const other = is_width ? height_field.value : width_field.value;
		letterhead.value[other] = is_width ? v / aspect_ratio.value : aspect_ratio.value * v;
	}
	letterhead.value._dirty = true;
}

function set_image(url) {
	if (!letterhead.value) return;
	if (!url) {
		letterhead.value[image_field.value] = "";
		letterhead.value._dirty = true;
		return;
	}
	get_image_dimensions(url)
		.then(({ width, height }) => {
			aspect_ratio.value = width / height;
			range_field.value = aspect_ratio.value > 1 ? width_field.value : height_field.value;
			let new_width = width > 200 ? 200 : width;
			let new_height = new_width / aspect_ratio.value;
			if (new_height > 80) {
				new_height = 80;
				new_width = aspect_ratio.value * new_height;
			}
			letterhead.value[image_field.value] = url;
			letterhead.value[width_field.value] = new_width;
			letterhead.value[height_field.value] = new_height;
			if (props.zone === "footer") {
				letterhead.value[source_field.value] = "Image";
			}
			letterhead.value._dirty = true;
		})
		.catch(() => {
			frappe.show_alert({ message: __("Could not load this image"), indicator: "orange" });
		});
}

function edit_html() {
	open_html_editor({
		title:
			props.zone === "header" ? __("Edit Letter Head HTML") : __("Edit Letter Head Footer"),
		initial_html: letterhead.value?.[html_content_field.value] || "",
		doctype: store.meta.value?.name,
		docname: store.preview_doc_name.value,
		on_save: (html) => {
			letterhead.value[html_content_field.value] = html;
			letterhead.value._dirty = true;
		},
	});
}
</script>

<style scoped>
.pfb-lh-zone-label {
	display: flex;
	align-items: center;
	gap: 6px;
	font-size: var(--text-tiny);
	font-weight: var(--weight-semibold);
	letter-spacing: 0;
	color: var(--gray-600);
	background: var(--surface-gray-1);
	border-bottom: 1px solid var(--gray-200);
	padding: 7px 14px;
	flex-shrink: 0;
}
</style>
