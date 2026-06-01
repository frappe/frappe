<template>
	<div class="pfb-insp-body">
		<!-- Zone label — footer only (matches original design; header has no zone label) -->
		<div v-if="zone === 'footer'" class="pfb-lh-zone-label">
			<span v-html="frappe.utils.icon('align-bottom', 'xs')"></span>
			{{ __("Letter Head Footer") }}
		</div>

		<!-- Based on toggle + letter head actions -->
		<div class="pfb-insp-section">
			<div class="pfb-insp-section-body" style="padding-top: 10px">
				<div class="pfb-insp-row">
					<span class="pfb-insp-label">{{ __("Based on") }}</span>
					<div class="pfb-seg">
						<button
							:class="{ active: zone_source === 'Image' }"
							@click="letterhead && (letterhead[source_field] = 'Image')"
						>
							{{ __("Image") }}
						</button>
						<button
							:class="{ active: zone_source === 'HTML' }"
							@click="letterhead && (letterhead[source_field] = 'HTML')"
						>
							{{ __("HTML") }}
						</button>
					</div>
				</div>
				<!-- Letter head selection buttons — always visible for header zone -->
				<template v-if="zone === 'header'">
					<div v-if="letterhead" class="pfb-lh-actions" style="margin-top: 4px">
						<button class="btn btn-xs btn-default" @click="lh_change_letterhead">
							{{ __("Change Letter Head") }}
						</button>
					</div>
					<div v-else class="pfb-lh-actions" style="margin-top: 4px">
						<p class="pfb-insp-hint text-muted">
							{{ __("No letter head selected.") }}
						</p>
						<button class="btn btn-xs btn-default" @click="lh_create_letterhead">
							{{ __("Create Letter Head") }}
						</button>
						<button class="btn btn-xs btn-default" @click="lh_change_letterhead">
							{{ __("Select Letter Head") }}
						</button>
					</div>
				</template>
			</div>
		</div>

		<!-- HTML section -->
		<div class="pfb-insp-section" v-if="zone_source === 'HTML'">
			<div class="pfb-insp-section-head" @click="open.html = !open.html">
				<span class="pfb-insp-section-label">{{ __("HTML") }}</span>
				<span
					class="pfb-insp-chevron"
					:class="{ collapsed: !open.html }"
					v-html="frappe.utils.icon('chevron-down', 'xs')"
				></span>
			</div>
			<div v-show="open.html" class="pfb-insp-section-body">
				<template v-if="letterhead">
					<div
						class="pfb-html-preview"
						v-if="letterhead[html_content_field]"
						v-html="letterhead[html_content_field]"
					></div>
					<div v-else class="pfb-insp-hint text-muted">
						{{ __("No HTML content yet.") }}
					</div>
					<button class="btn btn-xs btn-default pfb-lh-edit-btn" @click="edit_html">
						<span v-html="frappe.utils.icon('edit', 'xs')"></span>
						{{ __("Edit HTML") }}
					</button>
				</template>
				<template v-else>
					<p class="pfb-insp-hint text-muted">
						{{ __("No letter head selected.") }}
					</p>
				</template>
			</div>
		</div>

		<!-- Image section -->
		<div class="pfb-insp-section" v-if="zone_source === 'Image'">
			<div class="pfb-insp-section-head" @click="open.image = !open.image">
				<span class="pfb-insp-section-label">{{ __("Image") }}</span>
				<span
					class="pfb-insp-chevron"
					:class="{ collapsed: !open.image }"
					v-html="frappe.utils.icon('chevron-down', 'xs')"
				></span>
			</div>
			<div v-show="open.image" class="pfb-insp-section-body">
				<template v-if="letterhead">
					<!-- Alignment -->
					<div class="pfb-insp-row">
						<span class="pfb-insp-label">{{ __("Align") }}</span>
						<div class="pfb-seg">
							<button
								v-for="dir in ['Left', 'Center', 'Right']"
								:key="dir"
								:class="{ active: zone_align === dir }"
								@click="letterhead[align_field] = dir"
							>
								{{ __(dir) }}
							</button>
						</div>
					</div>
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
						<button class="btn btn-xs btn-default" @click="upload_image">
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
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, onMounted, ref } from "vue";
import { useStore } from "../../stores";
import { get_image_dimensions } from "../../utils";

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

const zone_source = computed(() => letterhead.value?.[source_field.value] ?? "Image");
const zone_align = computed(() => letterhead.value?.[align_field.value] ?? "Left");

const open = ref({ html: true, image: true });

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

function set_size(val) {
	if (!letterhead.value || !range_field.value) return;
	const v = parseFloat(val);
	letterhead.value[range_field.value] = v;
	if (aspect_ratio.value) {
		const is_width = range_field.value === width_field.value;
		const other = is_width ? height_field.value : width_field.value;
		letterhead.value[other] = is_width ? v / aspect_ratio.value : aspect_ratio.value * v;
	}
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
					letterhead.value._dirty = true;
				}
			});
		},
	});
}

function open_html_split_dialog({ title, initial_html, on_save }) {
	let d = new frappe.ui.Dialog({
		title,
		size: "extra-large",
		fields: [
			{
				fieldname: "split_layout",
				fieldtype: "HTML",
				options: `<div class="pfb-html-split">
					<div class="pfb-html-split-pane pfb-html-split-editor">
						<div class="pfb-html-split-label">${__("HTML")}</div>
						<div class="pfb-html-ctrl-host"></div>
					</div>
					<div class="pfb-html-split-divider"></div>
					<div class="pfb-html-split-pane pfb-html-split-preview">
						<div class="pfb-html-split-label">${__("Preview")}</div>
						<div class="pfb-html-preview-content"></div>
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

		if (preview) preview.innerHTML = initial_html || "";

		setTimeout(() => {
			if (ctrl.editor) {
				ctrl.editor.on(
					"change",
					frappe.utils.debounce(() => {
						if (preview) preview.innerHTML = ctrl.editor.getValue();
					}, 150)
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
.pfb-insp-body {
	flex: 1;
	overflow-y: auto;
	display: flex;
	flex-direction: column;
}

.pfb-insp-section {
	border-bottom: 1px solid var(--border-color);
}

.pfb-insp-section-head {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 10px 14px;
	cursor: pointer;
	user-select: none;
}

.pfb-insp-section-head:hover {
	background: var(--gray-50);
}

.pfb-insp-section-label {
	font-size: 10px;
	font-weight: 700;
	text-transform: uppercase;
	letter-spacing: 0.08em;
	color: var(--text-muted);
}

.pfb-insp-chevron {
	display: flex;
	align-items: center;
	color: var(--gray-400);
	transition: transform 0.15s;
}

.pfb-insp-chevron.collapsed {
	transform: rotate(-90deg);
}

.pfb-insp-section-body {
	padding: 4px 14px 12px;
	display: flex;
	flex-direction: column;
	gap: 10px;
}

.pfb-insp-row {
	display: grid;
	grid-template-columns: 80px 1fr;
	align-items: center;
	gap: 8px;
}

.pfb-insp-row--col {
	grid-template-columns: 1fr;
	gap: 4px;
}

.pfb-insp-label {
	font-size: var(--text-sm);
	color: var(--text-muted);
}

.pfb-seg {
	display: inline-flex;
	background: var(--gray-100);
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius);
	overflow: hidden;
	width: 100%;
}

.pfb-seg button {
	flex: 1;
	padding: 5px 6px;
	font-size: 11px;
	font-weight: 500;
	border: none;
	border-radius: 0;
	background: transparent;
	color: var(--text-muted);
	cursor: pointer;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	line-height: 1;
}

.pfb-seg button:not(:first-child) {
	border-left: 1px solid var(--border-color);
}

.pfb-seg button:hover {
	background: var(--gray-200);
	color: var(--text-color);
}

.pfb-seg button.active {
	background: var(--fg-color);
	color: var(--text-color);
	box-shadow: var(--shadow-xs);
}

.pfb-insp-hint {
	font-size: var(--text-sm);
	line-height: 1.5;
}

.pfb-lh-zone-label {
	display: flex;
	align-items: center;
	gap: 6px;
	font-size: 11px;
	font-weight: 600;
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

.pfb-lh-edit-btn {
	display: inline-flex;
	align-items: center;
	gap: 4px;
}

.pfb-html-preview {
	font-size: var(--text-sm);
	color: var(--text-muted);
	padding: 6px 8px;
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius);
	background: var(--gray-50);
	max-height: 100px;
	overflow: hidden;
	margin-bottom: 2px;
}
</style>
