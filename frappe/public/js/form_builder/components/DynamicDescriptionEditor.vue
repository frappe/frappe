<script setup>
import { computed } from "vue";
import { useStore } from "../store";

const props = defineProps({ read_only: Boolean });
const store = useStore();

const is_dynamic = computed({
	get: () => !!store.form.selected_field?.dynamic_description,
	set: (val) => {
		if (!val) {
			store.form.selected_field.dynamic_description = "";
		} else if (!store.form.selected_field.dynamic_description) {
			store.form.selected_field.dynamic_description = JSON.stringify({
				source_field: "",
				conditions: [],
				default: store.form.selected_field.description || "",
			});
			store.form.selected_field.description = "";
		}
	},
});

const config = computed({
	get: () => {
		if (!store.form.selected_field?.dynamic_description) return null;
		try {
			return JSON.parse(store.form.selected_field.dynamic_description);
		} catch {
			return null;
		}
	},
	set: (val) => {
		store.form.selected_field.dynamic_description = val ? JSON.stringify(val) : "";
	},
});

function all_layout_fields() {
	const no_value = frappe.model.no_value_type || [];
	const self_df = store.form.selected_field;
	const own = self_df?.fieldname;
	const result = [];

	// Self at the top — read directly from selected_field so unsaved options are visible
	if (own && self_df && !no_value.includes(self_df.fieldtype)) {
		result.push({
			value: own,
			label: self_df.label || own,
		});
	}

	for (const tab of store.form.layout?.tabs || []) {
		for (const section of tab.sections || []) {
			for (const column of section.columns || []) {
				for (const field of column.fields || []) {
					const df = field.df;
					// skip no-value types, blank fieldnames, and self (already added above)
					if (!df.fieldname || no_value.includes(df.fieldtype) || df.fieldname === own) {
						continue;
					}
					result.push({ value: df.fieldname, label: df.label || df.fieldname });
				}
			}
		}
	}
	return result;
}

function find_df_in_layout(fieldname) {
	for (const tab of store.form.layout?.tabs || []) {
		for (const section of tab.sections || []) {
			for (const column of section.columns || []) {
				for (const field of column.fields || []) {
					if (field.df.fieldname === fieldname) return field.df;
				}
			}
		}
	}
	return null;
}

const value_fields = computed(() => all_layout_fields());

const source_field_df = computed(() => ({
	fieldtype: "Select",
	label: __("Based on field"),
	options: [{ label: __("Select Field"), value: "" }, ...value_fields.value],
}));

const source_field_model = computed({
	get: () => config.value?.source_field || "",
	set: (val) => set_source_field(val),
});

const own_fieldname = computed(() => store.form.selected_field?.fieldname);

const source_df = computed(() => {
	const sf = config.value?.source_field;
	if (!sf) return null;
	// When source is self, use selected_field directly so live options on an
	// unsaved new field are always visible without a layout traversal.
	if (sf === own_fieldname.value) return store.form.selected_field;
	return find_df_in_layout(sf);
});

const source_is_select = computed(() => source_df.value?.fieldtype === "Select");

const source_options = computed(() => {
	if (!source_is_select.value) return [];
	return (source_df.value.options || "").split("\n").filter(Boolean);
});

const condition_value_df = computed(() => ({
	fieldtype: "Select",
	label: "",
	options: [
		{ label: __("Select value"), value: "" },
		...source_options.value.map((o) => ({ label: o, value: o })),
	],
}));

function set_source_field(fieldname) {
	// Prefer selected_field directly for self so unsaved options are available
	const actual_df =
		fieldname === own_fieldname.value
			? store.form.selected_field
			: find_df_in_layout(fieldname);
	let conditions = [];
	if (actual_df?.fieldtype === "Select") {
		conditions = (actual_df.options || "")
			.split("\n")
			.filter(Boolean)
			.map((o) => ({ value: o, description: "" }));
	}
	config.value = { ...config.value, source_field: fieldname, conditions };
}

function add_condition() {
	const c = config.value;
	config.value = { ...c, conditions: [...(c.conditions || []), { value: "", description: "" }] };
}

function remove_condition(i) {
	const c = config.value;
	config.value = { ...c, conditions: c.conditions.filter((_, idx) => idx !== i) };
}

function update_condition_value(i, val) {
	const c = config.value;
	config.value = {
		...c,
		conditions: c.conditions.map((cond, idx) =>
			idx === i ? { ...cond, value: val } : cond
		),
	};
}

function update_condition_description(i, val) {
	const c = config.value;
	config.value = {
		...c,
		conditions: c.conditions.map((cond, idx) =>
			idx === i ? { ...cond, description: val } : cond
		),
	};
}

function update_default(val) {
	config.value = { ...config.value, default: val };
}
</script>

<template>
	<div class="dynamic-description-editor">
		<div class="editor-header">
			<span class="field-label">{{ __("Description") }}</span>
			<div class="mode-toggle" role="group">
				<button
					type="button"
					class="mode-btn"
					:class="{ active: !is_dynamic }"
					:disabled="read_only"
					:title="__('Fixed description text')"
					@click="is_dynamic = false"
				>{{ __("Static") }}</button>
				<button
					type="button"
					class="mode-btn"
					:class="{ active: is_dynamic }"
					:disabled="read_only"
					:title="__('Description changes based on another field value')"
					@click="is_dynamic = true"
				>{{ __("Dynamic") }}</button>
			</div>
		</div>

		<!-- Static mode -->
		<div v-if="!is_dynamic">
			<textarea
				class="form-control desc-textarea"
				:value="store.form.selected_field.description"
				:disabled="read_only"
				rows="3"
				:placeholder="__('Enter field description...')"
				@input="store.form.selected_field.description = $event.target.value"
			></textarea>
		</div>

		<!-- Dynamic mode -->
		<div v-else-if="config" class="dynamic-editor">
			<div class="source-row">
				<SelectControl
					:df="source_field_df"
					:read_only="read_only"
					v-model="source_field_model"
				/>
			</div>

			<div v-if="config.source_field" class="conditions-block">
				<label class="sub-label">{{ __("Conditions") }}</label>

				<div
					v-for="(cond, i) in config.conditions"
					:key="i"
					class="condition-card"
				>
					<div class="condition-card-header">
						<span class="sub-label">{{ __("When value is") }}</span>
						<button
							v-if="!read_only"
							class="btn btn-xs remove-btn"
							type="button"
							:title="__('Remove')"
							@click="remove_condition(i)"
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								width="10"
								height="10"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2.5"
							>
								<line x1="18" y1="6" x2="6" y2="18"></line>
								<line x1="6" y1="6" x2="18" y2="18"></line>
							</svg>
						</button>
					</div>

					<SelectControl
						v-if="source_is_select"
						:df="condition_value_df"
						:modelValue="cond.value"
						:read_only="read_only"
						:no_label="true"
						@update:modelValue="update_condition_value(i, $event)"
					/>
					<input
						v-else
						type="text"
						class="form-control"
						:value="cond.value"
						:disabled="read_only"
						:placeholder="__('Value')"
						@input="update_condition_value(i, $event.target.value)"
					/>

					<label class="sub-label desc-label">{{ __("Description") }}</label>
					<textarea
						class="form-control desc-textarea"
						:value="cond.description"
						:disabled="read_only"
						rows="2"
						:placeholder="__('Description text')"
						@input="update_condition_description(i, $event.target.value)"
					></textarea>
				</div>

				<div v-if="!config.conditions.length" class="empty-conditions">
					{{ __("No conditions yet. Add one below.") }}
				</div>

				<button
					v-if="!read_only"
					class="btn btn-xs btn-default add-btn"
					type="button"
					@click="add_condition"
				>+ {{ __("Add Condition") }}</button>
			</div>

			<div class="default-row">
				<label class="sub-label">{{ __("Default") }}</label>
				<textarea
					class="form-control desc-textarea"
					:value="config.default"
					:disabled="read_only"
					rows="2"
					:placeholder="__('Shown when no condition matches')"
					@input="update_default($event.target.value)"
				></textarea>
			</div>
		</div>
	</div>
</template>

<style lang="scss" scoped>
.dynamic-description-editor {
	.editor-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: var(--margin-xs);

		.field-label {
			font-size: var(--text-sm);
			font-weight: 500;
			color: var(--text-color);
		}

		.mode-toggle {
			display: flex;
			gap: 2px;
			background: var(--fg-color);
			border: 1px solid var(--border-color);
			border-radius: var(--border-radius);
			padding: 2px;

			.mode-btn {
				font-size: var(--text-xs);
				font-weight: normal;
				cursor: pointer;
				margin: 0;
				padding: 2px 8px;
				border-radius: calc(var(--border-radius) - 2px);
				color: var(--text-muted);
				background: transparent;
				border: none;
				line-height: 1.5;
				transition: background 0.15s, color 0.15s;

				&.active {
					background: var(--primary);
					color: white;
				}

				&:not(.active):not(:disabled):hover {
					background: var(--hover-bg);
					color: var(--text-color);
				}

				&:disabled {
					cursor: default;
					opacity: 0.6;
				}
			}
		}
	}

	.desc-textarea {
		font-size: var(--text-sm);
		resize: vertical;
		min-height: 52px;
	}

	.dynamic-editor {
		display: flex;
		flex-direction: column;
		gap: var(--margin-sm);

		.sub-label {
			display: block;
			font-size: var(--text-xs);
			color: var(--text-muted);
			margin-bottom: 3px;
			font-weight: normal;
		}

		.conditions-block {
			display: flex;
			flex-direction: column;
			gap: var(--margin-xs);

			.condition-card {
				border: 1px solid var(--border-color);
				border-radius: var(--border-radius);
				padding: var(--padding-sm);

				.condition-card-header {
					display: flex;
					align-items: center;
					justify-content: space-between;
					margin-bottom: 3px;

					.sub-label {
						margin-bottom: 0;
					}

					.remove-btn {
						display: flex;
						align-items: center;
						justify-content: center;
						width: 20px;
						height: 20px;
						padding: 0;
						color: var(--text-muted);
						background: transparent;
						border: none;

						&:hover {
							color: var(--red);
						}
					}
				}

				.desc-label {
					margin-top: var(--margin-xs);
				}
			}

			.empty-conditions {
				font-size: var(--text-xs);
				color: var(--text-muted);
				font-style: italic;
				text-align: center;
				padding: var(--padding-sm) 0;
			}

			.add-btn {
				width: 100%;
				font-size: var(--text-xs);
			}
		}
	}
}
</style>
