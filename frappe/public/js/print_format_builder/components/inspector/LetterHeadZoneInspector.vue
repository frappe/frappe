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
					:label="__('Based on')"
					:model-value="zone_source"
					:options="[
						{ value: 'Image', label: __('Image') },
						{ value: 'HTML', label: __('HTML') },
					]"
					@update:model-value="set_source"
				/>
				<!-- Letter head selection buttons — always visible for header zone -->
				<template v-if="zone === 'header'">
					<div v-if="letterhead" class="pfb-lh-actions" style="margin-top: 4px">
						<button class="es-button" data-size="xs" @click="lh_change_letterhead">
							{{ __("Change Letter Head") }}
						</button>
					</div>
					<div v-else class="pfb-lh-actions" style="margin-top: 4px">
						<p class="pfb-insp-hint text-muted">
							{{ __("No letter head selected.") }}
						</p>
						<button class="es-button" data-size="xs" @click="lh_create_letterhead">
							{{ __("Create Letter Head") }}
						</button>
						<button class="es-button" data-size="xs" @click="lh_change_letterhead">
							{{ __("Select Letter Head") }}
						</button>
					</div>
				</template>
			</div>
		</div>

		<!-- HTML section -->
		<InspectorSection v-if="zone_source === 'HTML'" :label="__('HTML')">
			<template v-if="letterhead">
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
			</template>
			<template v-else>
				<p class="pfb-insp-hint text-muted">
					{{ __("No letter head selected.") }}
				</p>
			</template>
		</InspectorSection>

		<!-- Image section -->
		<InspectorSection v-if="zone_source === 'Image'" :label="__('Image')">
			<template v-if="letterhead">
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
				<!-- Size slider -->
				<div v-if="letterhead[image_field]" class="pfb-insp-row pfb-insp-row--col">
					<span class="pfb-insp-label">{{ __("Size") }}</span>
					<input
						class="pfb-lh-slider"
						type="range"
						min="20"
						:max="zone_size_max"
						:value="zone_size"
						@input="(e) => set_size(e.target.value)"
					/>
				</div>
				<!-- Actions -->
				<div class="pfb-lh-actions">
					<button class="es-button" data-size="xs" @click="upload_image">
						<span v-html="frappe.utils.icon('upload', 'xs')"></span>
						{{ letterhead[image_field] ? __("Change Image") : __("Upload Image") }}
					</button>
				</div>
			</template>
			<template v-else>
				<p class="pfb-insp-hint text-muted">
					{{ __("No letter head selected.") }}
				</p>
			</template>
		</InspectorSection>
	</div>
</template>

<script setup>
import { computed, inject, onMounted, ref } from "vue";
import { useStore } from "../../stores";
import { get_image_dimensions, render_jinja_html } from "../../utils";
import SegmentedRow from "./SegmentedRow.vue";
import InspectorSection from "./InspectorSection.vue";

const props = defineProps({
	zone: { type: String, required: true },
});

const store = inject("$store");
const { letterhead } = useStore();

const source_field = computed(() => (props.zone === "header" ? "source" : "footer_source"));
const align_field = computed(() => (props.zone === "header" ? "align" : "footer_align"));
const image_field = computed(() => (props.zone === "header" ? "image" : "footer_image"));
const html_content_field = computed(() => (props.zone === "header" ? "content" : "footer"));
const width_field = computed(() =>
	props.zone === "header" ? "image_width" : "footer_image_width"
);
const height_field = computed(() =>
	props.zone === "header" ? "image_height" : "footer_image_height"
);

const zone_source = computed(() => letterhead.value?.[source_field.value] || "Image");
const zone_align = computed(() => letterhead.value?.[align_field.value] ?? "Left");

const aspect_ratio = ref(null);
const range_field = ref(null);

onMounted(() => {
	const img = letterhead.value?.[image_field.value];
	if (img) {
		get_image_dimensions(img).then(({ width, height }) => {
			aspect_ratio.value = width / height;
			range_field.value = aspect_ratio.value > 1 ? width_field.value : height_field.value;
		});
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

function upload_image() {
	new frappe.ui.FileUploader({
		folder: "Home/Attachments",
		on_success: (file_doc) => {
			get_image_dimensions(file_doc.file_url).then(({ width, height }) => {
				aspect_ratio.value = width / height;
				range_field.value =
					aspect_ratio.value > 1 ? width_field.value : height_field.value;
				let new_width = width > 200 ? 200 : width;
				let new_height = new_width / aspect_ratio.value;
				if (new_height > 80) {
					new_height = 80;
					new_width = aspect_ratio.value * new_height;
				}
				letterhead.value[image_field.value] = file_doc.file_url;
				letterhead.value[width_field.value] = new_width;
				letterhead.value[height_field.value] = new_height;
				if (props.zone === "footer") {
					letterhead.value[source_field.value] = "Image";
				}
				letterhead.value._dirty = true;
			});
		},
	});
}

function open_html_split_dialog({ title, initial_html, on_save, doctype, docname }) {
	let d = new frappe.ui.Dialog({
		title,
		size: "extra-large",
		fields: [
			{
				fieldname: "split_layout",
				fieldtype: "HTML",
				options: `<style>
					.pfb-lh-split{display:flex;height:480px;gap:0;overflow:hidden;margin:-15px}
					.pfb-lh-split-pane{display:flex;flex-direction:column;flex:1;min-width:0;overflow:hidden}
					.pfb-lh-split-divider{width:1px;background:var(--border-color);flex-shrink:0}
					.pfb-lh-split-label{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--text-muted);padding:10px 12px 8px;border-bottom:1px solid var(--border-color);flex-shrink:0}
					.pfb-lh-split-ctrl{flex:1;overflow:hidden}
					.pfb-lh-split-ctrl .pfb-html-ctrl-host{height:100%}
					.pfb-lh-preview-iframe{flex:1;width:100%;border:none;background:#fff}
				</style>
				<div class="pfb-lh-split">
					<div class="pfb-lh-split-pane">
						<div class="pfb-lh-split-label">${__("HTML")}</div>
						<div class="pfb-lh-split-ctrl"><div class="pfb-html-ctrl-host"></div></div>
					</div>
					<div class="pfb-lh-split-divider"></div>
					<div class="pfb-lh-split-pane">
						<div class="pfb-lh-split-label">${__("Preview")}</div>
						<iframe class="pfb-html-preview-content pfb-lh-preview-iframe" frameborder="0"></iframe>
					</div>
				</div>`,
			},
		],
		primary_action_label: __("Save"),
		primary_action: () => {
			const val = d._html_ctrl?.get_value?.() ?? "";
			on_save(frappe.dom.remove_script_and_style(val));
			d.hide();
		},
	});
	d.show();

	const PREVIEW_CSS = `
		* { box-sizing: border-box; }
		body { margin: 0; padding: 12px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; color: #333; line-height: 1.5; }
		img { max-width: 100%; height: auto; display: block; }
		table { border-collapse: collapse; width: 100%; }
		td, th { vertical-align: top; }
	`;

	function write_to_iframe(iframe, html) {
		const doc = iframe.contentDocument || iframe.contentWindow?.document;
		if (!doc) return;
		doc.open();
		doc.write(
			`<!DOCTYPE html><html><head><meta charset="utf-8"><style>${PREVIEW_CSS}</style></head><body>${html}</body></html>`
		);
		doc.close();
	}

	async function update_preview(iframe, html) {
		if (!iframe) return;
		write_to_iframe(iframe, await render_jinja_html(html || "", doctype, docname));
	}

	setTimeout(() => {
		const host = d.$wrapper.find(".pfb-html-ctrl-host")[0];
		const preview = d.$wrapper.find(".pfb-html-preview-content")[0];
		if (!host) return;

		const ctrl = frappe.ui.form.make_control({
			parent: host,
			df: {
				fieldtype: "Code",
				fieldname: "html_code",
				options: "HTML",
				show_label: false,
			},
			render_input: true,
		});
		ctrl.set_value(initial_html || "");
		d._html_ctrl = ctrl;

		update_preview(preview, initial_html || "");

		setTimeout(() => {
			if (ctrl.editor) {
				ctrl.editor.on(
					"change",
					frappe.utils.debounce(() => {
						update_preview(preview, ctrl.editor.getValue());
					}, 400)
				);
				ctrl.editor.refresh();
			}
		}, 300);
	}, 200);
}

function edit_html() {
	open_html_split_dialog({
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

function lh_change_letterhead() {
	let d = new frappe.ui.Dialog({
		title: __("Change Letter Head"),
		fields: [
			{
				label: __("Letter Head"),
				fieldname: "letterhead",
				fieldtype: "Link",
				options: "Letter Head",
			},
		],
		primary_action: ({ letterhead: lh }) => {
			if (lh) store.change_letterhead(lh);
			d.hide();
		},
	});
	d.show();
}

function lh_create_letterhead() {
	let d = new frappe.ui.Dialog({
		title: __("Create Letter Head"),
		fields: [{ label: __("Letter Head Name"), fieldname: "name", fieldtype: "Data" }],
		primary_action: ({ name }) => {
			return frappe.db
				.insert({ doctype: "Letter Head", letter_head_name: name, source: "Image" })
				.then((doc) => {
					d.hide();
					store.change_letterhead(doc.name);
				});
		},
	});
	d.show();
}
</script>

<style scoped>
.pfb-lh-zone-label {
	display: flex;
	align-items: center;
	gap: 6px;
	font-size: var(--text-tiny);
	font-weight: var(--weight-semibold);
	text-transform: uppercase;
	letter-spacing: 0.06em;
	color: var(--blue-500);
	background: var(--blue-50);
	border-bottom: 1px solid var(--blue-200);
	padding: 7px 14px;
	flex-shrink: 0;
}

.pfb-lh-slider {
	width: 100%;
	accent-color: var(--primary);
}

.pfb-lh-actions {
	display: flex;
	flex-direction: column;
	gap: 6px;
}
</style>
