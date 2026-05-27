<template>
	<div class="sidebar-wrapper">
		<div class="form-sidebar">
			<details class="sidebar-section" open>
				<summary class="sidebar-section-title">
					{{ __("Page Settings") }}
					<span
						class="chevron-icon"
						v-html="frappe.utils.icon('chevron-down', 'sm')"
					></span>
				</summary>
				<div class="sidebar-section-body">
					<div class="margin-controls">
						<div class="form-group" v-for="df in margins" :key="df.fieldname">
							<label class="control-label">{{ df.label }}</label>
							<input
								type="number"
								class="form-control form-control-sm"
								:value="print_format[df.fieldname]"
								min="0"
								@change="(e) => update_margin(df.fieldname, e.target.value)"
							/>
						</div>
					</div>
					<div class="form-group">
						<label class="control-label">{{ __("Google Font") }}</label>
						<select class="form-control form-control-sm" v-model="print_format.font">
							<option v-for="font in google_fonts" :value="font">{{ font }}</option>
						</select>
					</div>
					<div class="form-group">
						<label class="control-label">{{ __("Font Size") }}</label>
						<input
							type="number"
							class="form-control form-control-sm"
							placeholder="12, 13, 14"
							:value="print_format.font_size"
							@change="(e) => (print_format.font_size = parseFloat(e.target.value))"
						/>
					</div>
					<div class="form-group">
						<label class="control-label">{{ __("Page Number") }}</label>
						<select
							class="form-control form-control-sm"
							v-model="print_format.page_number"
						>
							<option v-for="p in page_number_positions" :value="p.value">
								{{ p.label }}
							</option>
						</select>
					</div>
				</div>
			</details>

			<details class="sidebar-section fields-section" open>
				<summary class="sidebar-section-title">
					{{ __("Fields") }}
					<span
						class="chevron-icon"
						v-html="frappe.utils.icon('chevron-down', 'sm')"
					></span>
				</summary>
				<div class="sidebar-section-body">
					<input
						class="mb-2 form-control form-control-sm"
						type="text"
						:placeholder="__('Search fields')"
						v-model="search_text"
					/>

					<!-- When NOT searching: show two labeled groups -->
					<template v-if="!search_text">
						<div v-if="layout_fields.length" class="field-group">
							<div class="field-group-label">{{ __("Layout") }}</div>
							<draggable
								:list="layout_fields"
								:group="{ name: 'fields', pull: 'clone', put: false }"
								:sort="false"
								:clone="clone_field"
								item-key="fieldname"
							>
								<template #item="{ element }">
									<div
										class="sidebar-field"
										:title="element.fieldname"
										@click="add_to_layout(element)"
									>
										<span>{{ element.label }}</span>
										<svg class="icon icon-xs text-muted">
											<use href="#icon-plus"></use>
										</svg>
									</div>
								</template>
							</draggable>
						</div>
						<div class="field-group mt-2">
							<div class="field-group-label">{{ __("Document Fields") }}</div>
							<draggable
								class="fields-container"
								:list="doc_fields"
								:group="{ name: 'fields', pull: 'clone', put: false }"
								:sort="false"
								:clone="clone_field"
								item-key="fieldname"
							>
								<template #item="{ element }">
									<div
										class="sidebar-field"
										:title="element.fieldname"
										@click="add_to_layout(element)"
									>
										<span>{{ element.label }}</span>
										<svg class="icon icon-xs text-muted">
											<use href="#icon-plus"></use>
										</svg>
									</div>
								</template>
							</draggable>
						</div>
					</template>

					<!-- When searching: flat list of all matching fields -->
					<template v-else>
						<draggable
							class="fields-container"
							:list="all_fields"
							:group="{ name: 'fields', pull: 'clone', put: false }"
							:sort="false"
							:clone="clone_field"
							item-key="fieldname"
						>
							<template #item="{ element }">
								<div
									class="sidebar-field"
									:title="element.fieldname"
									@click="add_to_layout(element)"
								>
									<span>{{ element.label }}</span>
									<svg class="icon icon-xs text-muted">
										<use href="#icon-plus"></use>
									</svg>
								</div>
							</template>
						</draggable>
					</template>
				</div>
			</details>
		</div>
	</div>
</template>

<script setup>
import draggable from "vuedraggable";
import { get_table_columns, pluck } from "./utils";
import { useStore } from "./store";
import { computed, onMounted, ref, watch, inject } from "vue";

let search_text = ref("");
let google_fonts = ref([]);

let store = inject("$store");
let { meta, print_format, layout } = useStore();

function update_margin(fieldname, value) {
	value = parseFloat(value);
	if (value < 0) value = 0;
	print_format.value[fieldname] = value;
}

function clone_field(df) {
	let cloned = pluck(df, [
		"label",
		"fieldname",
		"fieldtype",
		"options",
		"table_columns",
		"html",
		"field_template",
	]);
	if (cloned.custom) {
		cloned.fieldname += "_" + frappe.utils.get_random(8);
	}
	return cloned;
}

function add_to_layout(df) {
	const sections = layout.value?.sections;
	if (!sections || !sections.length) return;
	const last_section = sections.filter((s) => !s.remove).slice(-1)[0];
	if (!last_section) return;
	const last_column = last_section.columns.slice(-1)[0];
	if (!last_column) return;
	last_column.fields.push(clone_field(df));
}

function build_field(df) {
	let out = {
		label: df.label,
		fieldname: df.fieldname,
		fieldtype: df.fieldtype,
		options: df.options,
	};
	if (df.fieldtype == "Table") {
		out.table_columns = get_table_columns(df);
	}
	return out;
}

let all_fields = computed(() => {
	const special = [
		{
			label: __("Custom HTML"),
			fieldname: "custom_html",
			fieldtype: "HTML",
			html: "",
			custom: 1,
		},
		{ label: __("ID (name)"), fieldname: "name", fieldtype: "Data" },
		{ label: __("Spacer"), fieldname: "spacer", fieldtype: "Spacer", custom: 1 },
		{ label: __("Divider"), fieldname: "divider", fieldtype: "Divider", custom: 1 },
		...print_templates.value,
	];
	const doc = meta.value.fields
		.filter((df) => !["Section Break", "Column Break"].includes(df.fieldtype))
		.map(build_field);

	return [...special, ...doc].filter((df) => {
		if (!search_text.value) return true;
		const q = search_text.value.toLowerCase();
		return (
			df.fieldname.toLowerCase().includes(q) ||
			(df.label && df.label.toLowerCase().includes(q))
		);
	});
});

let layout_fields = computed(() =>
	all_fields.value.filter(
		(df) => df.custom || ["HTML", "Spacer", "Divider", "Field Template"].includes(df.fieldtype)
	)
);

let doc_fields = computed(() =>
	all_fields.value.filter(
		(df) =>
			!df.custom && !["HTML", "Spacer", "Divider", "Field Template"].includes(df.fieldtype)
	)
);

let print_templates = computed(() => {
	let templates = print_format.value.__onload?.print_templates || [];
	return templates.map((template) => {
		let df;
		if (template.field) {
			df = frappe.meta.get_docfield(meta.value.name, template.field);
		} else {
			df = { label: template.name, fieldname: frappe.scrub(template.name) };
		}
		return {
			label: `${__(df.label, null, df.parent)} (${__("Field Template")})`,
			fieldname: df.fieldname + "_template",
			fieldtype: "Field Template",
			field_template: template.name,
		};
	});
});

let margins = computed(() => [
	{ label: __("Top"), fieldname: "margin_top" },
	{ label: __("Bottom"), fieldname: "margin_bottom" },
	{ label: __("Left", null, "alignment"), fieldname: "margin_left" },
	{ label: __("Right", null, "alignment"), fieldname: "margin_right" },
]);

let page_number_positions = computed(() => [
	{ label: __("Hide"), value: "Hide" },
	{ label: __("Top Left"), value: "Top Left" },
	{ label: __("Top Center"), value: "Top Center" },
	{ label: __("Top Right"), value: "Top Right" },
	{ label: __("Bottom Left"), value: "Bottom Left" },
	{ label: __("Bottom Center"), value: "Bottom Center" },
	{ label: __("Bottom Right"), value: "Bottom Right" },
]);

onMounted(() => {
	let method = "frappe.printing.page.print_format_builder.print_format_builder.get_google_fonts";
	frappe.call(method).then((r) => {
		google_fonts.value = r.message || [];
		if (!google_fonts.value.includes(print_format.value.font)) {
			google_fonts.value.push(print_format.value.font);
		}
	});
});

watch(print_format, () => (store.dirty.value = true), { deep: true });
</script>

<style scoped>
.sidebar-wrapper {
	width: 260px;
	flex-shrink: 0;
	height: calc(100vh - 95px);
	overflow-y: auto;
}

.form-control {
	background: var(--control-bg-on-gray);
}

.margin-controls {
	display: flex;
	gap: 0.4rem;
	margin-bottom: 0.5rem;
}

.margin-controls .form-group {
	flex: 1;
	margin-bottom: 0;
}

.margin-controls .control-label {
	font-size: 10px;
	margin-bottom: 2px;
}

.sidebar-section {
	border-bottom: 1px solid var(--border-color);
	margin-bottom: 0.25rem;
}

.sidebar-section-title {
	font-size: var(--text-sm);
	font-weight: 600;
	padding: 0.5rem 0;
	cursor: pointer;
	user-select: none;
	list-style: none;
	display: flex;
	align-items: center;
	justify-content: space-between;
}

.chevron-icon {
	color: var(--text-muted);
	transition: transform 0.15s;
	display: flex;
	align-items: center;
}

details:not([open]) .chevron-icon {
	transform: rotate(-90deg);
}

.sidebar-section-body {
	padding-bottom: 0.75rem;
}

.field-group {
	display: flex;
	flex-direction: column;
	gap: 0;
}

.field-group-label {
	font-size: 10px;
	font-weight: 600;
	text-transform: uppercase;
	color: var(--text-muted);
	letter-spacing: 0.05em;
	margin-bottom: 0.25rem;
	margin-top: 0.25rem;
}

.sidebar-field {
	display: flex;
	justify-content: space-between;
	align-items: center;
	width: 100%;
	background-color: var(--bg-light-gray);
	border-radius: var(--border-radius);
	border: 1px dashed var(--gray-400);
	padding: 0.4rem 0.6rem;
	font-size: var(--text-sm);
	cursor: grab;
	margin-top: 0.35rem;
}

.sidebar-field:hover {
	background-color: var(--gray-100);
	border-color: var(--gray-500);
}

.sidebar-field .icon {
	opacity: 0;
	transition: opacity 0.1s;
	margin-right: 0;
	flex-shrink: 0;
}

.sidebar-field:hover .icon {
	opacity: 1;
}
</style>
