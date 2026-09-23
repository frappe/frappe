<template>
	<div class="pfb-insp-body">
		<InspectorSection :label="__('Table')">
			<LabelField
				v-model="selected_field.label"
				:label="__('Title')"
				:placeholder="__('Table title')"
				show-toggle
				:show-label="__('Show title')"
				:show="selected_field.show_label"
				@update:show="(v) => (selected_field.show_label = v)"
			/>
			<!-- Style: one look = one (table_style, table_bordered) pair -->
			<DropdownRow
				:label="__('Style')"
				:model-value="table_look ?? ''"
				:options="table_look_opts"
				:placeholder="table_look === null ? __('Custom') : ''"
				@update:model-value="set_table_look"
			/>
			<SegmentedRow
				:label="__('Header')"
				:model-value="table_header"
				:options="[
					{ value: 'styled', label: __('Styled') },
					{ value: 'plain', label: __('Plain') },
					{ value: 'none', label: __('None') },
				]"
				@update:model-value="(v) => (selected_field.table_header = v)"
			/>
			<StepperRow
				:label="__('Cell padding')"
				:model-value="table_cell_padding"
				:base="7"
				unit="px"
				:placeholder="__('auto')"
				allow-empty
				@update:model-value="set_cell_padding"
			/>
			<StepperRow
				:label="__('Radius')"
				:model-value="table_radius"
				unit="px"
				:placeholder="__('none')"
				allow-empty
				@update:model-value="set_table_radius"
			/>
			<StepperRow
				:label="__('Min height')"
				:model-value="table_min_height"
				:base="100"
				:step="10"
				unit="px"
				:placeholder="__('auto')"
				allow-empty
				@update:model-value="(v) => set_field_prop('table_min_height', v)"
			/>
		</InspectorSection>

		<InspectorSection :label="__('Columns')" :padded="false">
			<template #head>
				<span class="pfb-insp-col-count text-muted">{{
					(selected_field.table_columns || []).length
				}}</span>
			</template>
			<div>
				<!-- Add column picker -->
				<div class="pfb-col-add-row top" v-if="available_columns.length">
					<Autocomplete
						:options="available_column_opts"
						:placeholder="__('Add column...')"
						@select="pick_column"
					/>
				</div>
				<div v-else class="pfb-insp-hint text-muted pfb-col-add-row top">
					{{ __("All available columns added.") }}
				</div>
				<!-- Column list -->
				<draggable
					:list="selected_field.table_columns"
					handle=".pfb-col-drag"
					:animation="150"
					item-key="fieldname"
					class="pfb-col-list"
				>
					<template #item="{ element: col, index: ci }">
						<div class="pfb-col-item">
							<div class="pfb-col-row">
								<span
									class="pfb-col-drag"
									v-html="frappe.utils.icon('grip', 'xs')"
								></span>
								<input
									class="pfb-col-label-input"
									type="text"
									v-model="col.label"
									:placeholder="col.fieldname"
									:title="col.fieldname"
								/>
								<button
									class="es-button"
									data-size="xs"
									data-icon-button="true"
									:data-variant="
										expanded_col === ci || col.merged_fields?.length
											? 'subtle'
											: 'ghost'
									"
									:title="__('Merge fields')"
									@click="expanded_col = expanded_col === ci ? null : ci"
									v-html="frappe.utils.icon('settings-2', 'xs')"
								></button>
								<button
									class="es-button"
									data-size="xs"
									data-variant="ghost"
									data-theme="red"
									data-icon-button="true"
									:title="__('Remove column')"
									@click="remove_table_column(ci)"
									v-html="frappe.utils.icon('x', 'xs')"
								></button>
							</div>

							<!-- Per-column merged-fields editor: reuses inspector primitives -->
							<div v-if="expanded_col === ci" class="pfb-col-editor">
								<div class="pfb-insp-section-body">
									<StepperRow
										:label="__('Width')"
										:model-value="col.width"
										:min="5"
										:step="5"
										unit="%"
										@update:model-value="(v) => set_width(col, v)"
									/>
								</div>
								<draggable
									:list="col.merged_fields"
									handle=".pfb-merge-drag"
									:animation="150"
									item-key="fieldname"
									class="pfb-col-list"
								>
									<template #item="{ element: mf, index: mi }">
										<div class="pfb-col-row">
											<span
												class="pfb-merge-drag"
												v-html="frappe.utils.icon('grip', 'xs')"
											></span>
											<span
												class="pfb-insp-label"
												style="
													flex: 1;
													min-width: 0;
													color: var(--text-color);
												"
												>{{ merge_field_label(mf) }}</span
											>
											<select
												v-if="!is_image_merge(mf)"
												class="pfb-insp-select"
												style="width: 104px; flex: none"
												v-model="mf.style"
												:title="__('Text style')"
											>
												<option
													v-for="s in merge_style_opts"
													:key="s.value"
													:value="s.value"
												>
													{{ s.label }}
												</option>
											</select>
											<div v-else :title="__('Image size')">
												<Stepper
													sm
													:min="16"
													:value="col.image_size || 40"
													unit="px"
													@decrement="adjust_image_size(col, -4)"
													@increment="adjust_image_size(col, 4)"
													@input="(v) => set_image_size(col, v)"
												/>
											</div>
											<button
												class="es-button"
												data-size="xs"
												data-variant="ghost"
												data-theme="red"
												data-icon-button="true"
												:title="__('Remove field')"
												@click="remove_merged_field(col, mi)"
												v-html="frappe.utils.icon('x', 'xs')"
											></button>
										</div>
									</template>
								</draggable>
								<div class="pfb-col-add-row" v-if="merge_field_opts(col).length">
									<Autocomplete
										:options="merge_field_opts(col)"
										:placeholder="__('Add field...')"
										@select="(opt) => add_merged_field(col, opt.value)"
									/>
								</div>
								<div
									v-if="col.merged_fields && col.merged_fields.length"
									class="pfb-merge-direction"
								>
									<SegmentedRow
										:label="__('Direction')"
										:model-value="col.merge_direction || 'vertical'"
										:options="merge_direction_opts"
										@update:model-value="(v) => (col.merge_direction = v)"
									/>
								</div>
								<TextRow
									class="pfb-col-cond"
									stacked
									:label="__('Show column when')"
									:placeholder="__('e.g. doc.apply_discount')"
									:model-value="col.column_condition || ''"
									@update:model-value="(v) => (col.column_condition = v)"
								/>
							</div>
						</div>
					</template>
				</draggable>
			</div>
		</InspectorSection>

		<InspectorSection :label="__('Style')" :init-open="false" :padded="false">
			<div class="pfb-insp-section-body">
				<ColorField
					v-if="table_header === 'styled'"
					:label="__('Header')"
					:model-value="table_header_bg"
					:placeholder="__('Default')"
					@update:model-value="(v) => set_field_prop('table_header_bg', v)"
				/>
				<ColorField
					v-if="has_lines"
					:label="__('Border')"
					:model-value="table_border_color"
					:placeholder="__('Default')"
					@update:model-value="(v) => set_field_prop('table_border_color', v)"
				/>
			</div>
			<StyleSection :label="__('Custom CSS')" v-model="selected_field.custom_style" />
		</InspectorSection>

		<InspectorSection :label="__('Visibility')" :padded="false">
			<VisibilitySection v-model="selected_field.visible_if" />
			<TextRow
				class="pfb-row-cond"
				stacked
				:label="__('Show row when')"
				:placeholder="__('e.g. row.qty > 0')"
				:model-value="selected_field.row_condition || ''"
				@update:model-value="(v) => (selected_field.row_condition = v)"
			>
				<p class="pfb-insp-hint text-muted">
					{{ __("Leave blank to show every row. Reference the row with") }}
					<code>row.fieldname</code>.
				</p>
			</TextRow>
		</InspectorSection>
	</div>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import draggable from "vuedraggable";
import Autocomplete from "../../../vue-components/Autocomplete.vue";
import LabelField from "./LabelField.vue";
import DropdownRow from "./DropdownRow.vue";
import TextRow from "./TextRow.vue";
import SegmentedRow from "./SegmentedRow.vue";
import InspectorSection from "./InspectorSection.vue";
import StepperRow from "./StepperRow.vue";
import Stepper from "./Stepper.vue";
import StyleSection from "./StyleSection.vue";
import ColorField from "./ColorField.vue";
import VisibilitySection from "./VisibilitySection.vue";
import { useSelectedField } from "./useSelectedField";
import { is_merge_image } from "../../fieldtypes";
import { clamp_column_width } from "../../utils";

const { selected_field, set_field_prop } = useSelectedField();

let table_style = computed(() => selected_field.value?.table_style ?? "lined");
let table_bordered = computed(() => selected_field.value?.table_bordered ?? true);
let table_header = computed(() => selected_field.value?.table_header ?? "styled");
let table_cell_padding = computed(() => selected_field.value?.table_cell_padding ?? null);
let table_radius = computed(() => selected_field.value?.table_radius ?? null);
let table_min_height = computed(() => selected_field.value?.table_min_height ?? null);
let table_header_bg = computed(() => selected_field.value?.table_header_bg ?? "");
let table_border_color = computed(() => selected_field.value?.table_border_color ?? "");
let has_lines = computed(
	() =>
		table_bordered.value !== false ||
		table_style.value === "lined" ||
		table_header.value === "plain"
);

const set_cell_padding = (v) => set_field_prop("table_cell_padding", v);
const set_table_radius = (v) => set_field_prop("table_radius", v);

const LOOKS = {
	grid: { style: "lined", bordered: true },
	rows: { style: "lined", bordered: false },
	striped: { style: "striped", bordered: false },
	clean: { style: "plain", bordered: false },
};

const table_look_opts = [
	{ value: "grid", label: __("Grid") },
	{ value: "rows", label: __("Rows") },
	{ value: "striped", label: __("Striped") },
	{ value: "clean", label: __("None") },
];

let table_look = computed(
	() =>
		Object.keys(LOOKS).find(
			(k) =>
				LOOKS[k].style === table_style.value && LOOKS[k].bordered === table_bordered.value
		) ?? null
);

function set_table_look(look) {
	const { style, bordered } = LOOKS[look];
	set_field_prop("table_style", style, "lined");
	set_field_prop("table_bordered", bordered, true);
}

let child_value_fields = computed(() => {
	const dt = selected_field.value?.options;
	const meta = dt && frappe.get_meta(dt);
	if (!meta) return [];
	return meta.fields.filter((f) => !frappe.model.no_value_type.includes(f.fieldtype));
});

function to_field_opts(fields) {
	return fields.map((f) => ({
		label: f.label || f.fieldname,
		value: f.fieldname,
		badge: f.fieldtype,
	}));
}

let available_columns = computed(() => {
	if (!selected_field.value?.options) return [];
	const existing = new Set((selected_field.value.table_columns || []).map((c) => c.fieldname));
	const standard = [{ label: __("Sr No."), fieldname: "idx", fieldtype: "Data" }];
	return standard
		.concat(child_value_fields.value.filter((f) => f.fieldname !== "name"))
		.filter((f) => !existing.has(f.fieldname));
});

let available_column_opts = computed(() => to_field_opts(available_columns.value));

function pick_column(opt) {
	const meta = frappe.get_meta(selected_field.value.options);
	let entry;
	if (opt.value === "idx") {
		entry = { label: __("Sr No."), fieldname: "idx", fieldtype: "Data", width: 10 };
	} else {
		const df = meta?.fields.find((f) => f.fieldname === opt.value);
		if (!df) return;
		entry = {
			label: df.label,
			fieldname: df.fieldname,
			fieldtype: df.fieldtype,
			options: df.options,
			width: 10,
		};
	}
	if (!selected_field.value.table_columns) selected_field.value.table_columns = [];
	selected_field.value.table_columns = [...selected_field.value.table_columns, entry];
}

function remove_table_column(idx) {
	selected_field.value.table_columns.splice(idx, 1);
	selected_field.value.table_columns = [...selected_field.value.table_columns];
	expanded_col.value = null;
}

watch(selected_field, () => (expanded_col.value = null));

function set_width(col, value) {
	col.width = clamp_column_width(value);
}

let expanded_col = ref(null);

const merge_style_opts = [
	{ value: "primary", label: __("Primary") },
	{ value: "secondary", label: __("Secondary") },
	{ value: "mono-sm", label: __("Code") },
	{ value: "muted-sm", label: __("Muted") },
];

const merge_direction_opts = [
	{ value: "vertical", label: __("Vertical") },
	{ value: "horizontal", label: __("Horizontal") },
];

function find_field(fieldname) {
	return child_value_fields.value.find((f) => f.fieldname === fieldname);
}

function merge_field_label(mf) {
	return find_field(mf.fieldname)?.label || mf.fieldname;
}

function merge_field_opts(col) {
	const used = new Set([col.fieldname, ...(col.merged_fields || []).map((m) => m.fieldname)]);
	return to_field_opts(child_value_fields.value.filter((f) => !used.has(f.fieldname)));
}

function is_image_merge(mf) {
	return is_merge_image(mf);
}

function ensure_merged(col) {
	if (!Array.isArray(col.merged_fields)) col.merged_fields = [];
	return col.merged_fields;
}

function add_merged_field(col, fieldname) {
	const f = find_field(fieldname);
	const mf = ensure_merged(col);
	if (f)
		mf.push({
			fieldname: f.fieldname,
			fieldtype: f.fieldtype,
			style: mf.length ? "muted-sm" : "secondary",
		});
}

function remove_merged_field(col, mi) {
	col.merged_fields.splice(mi, 1);
}

function adjust_image_size(col, delta) {
	col.image_size = Math.max(16, Math.min(200, (col.image_size || 40) + delta));
}

function set_image_size(col, value) {
	const v = parseInt(value);
	col.image_size = isNaN(v) ? 40 : Math.max(16, Math.min(200, v));
}
</script>

<style scoped>
.pfb-col-label-input {
	flex: 1;
	min-width: 0;
	font-size: var(--text-sm);
	border: 1px solid transparent;
	border-radius: var(--radius);
	background: transparent;
	padding: 1px 4px;
	outline: none;
}

.pfb-col-label-input:hover {
	border-color: var(--gray-300);
}

.pfb-col-label-input:focus {
	border-color: var(--gray-500);
	background: var(--fg-color);
}

/* the column picker sits above its list, so the divider belongs on the other side */
.pfb-col-add-row.top {
	padding: 8px 14px;
	border-top: none;
	border-bottom: 1px solid var(--gray-100);
}

.pfb-col-editor .pfb-merge-drag {
	color: var(--gray-400);
}

.pfb-merge-drag {
	cursor: grab;
	color: var(--gray-300);
	display: flex;
	align-items: center;
	flex-shrink: 0;
}

.pfb-merge-drag:hover {
	color: var(--gray-500);
}

.pfb-merge-direction {
	padding: 8px 14px 10px;
	border-top: 1px solid var(--gray-100);
}

.pfb-col-cond {
	padding: 8px 14px 10px;
	border-top: 1px solid var(--gray-100);
}

.pfb-row-cond {
	padding: 0 14px 12px;
}
</style>
