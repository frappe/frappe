<script setup>
import { computed } from "vue";
import { useLayoutBuilderStore, STRUCTURAL_TYPES } from "../store";

const props = defineProps(["field"]);
const store = useLayoutBuilderStore();

const base = computed(() => store.base_meta[props.field.fieldname] || {});
const fieldtype = computed(() => base.value.fieldtype || "");
const is_structural = computed(() => STRUCTURAL_TYPES.has(fieldtype.value));
const is_selected = computed(() => store.selected_field?.fieldname === props.field.fieldname);
const is_hidden = computed(() => !!props.field.hidden);

const fieldtype_icon = {
	"Section Break": "es-line-layout-rows",
	"Column Break": "es-line-columns",
	"Tab Break": "es-line-tab",
	Table: "es-line-table",
	Link: "es-line-link",
	Check: "es-line-check-circle",
	Date: "es-line-calendar",
	Datetime: "es-line-clock",
	Int: "es-line-hash",
	Float: "es-line-decimal",
	Currency: "es-line-currency",
	Text: "es-line-text",
	"Small Text": "es-line-text",
	Code: "es-line-code",
	Select: "es-line-list",
	Attach: "es-line-file-upload",
	"Attach Image": "es-line-image",
};

const icon = computed(() => fieldtype_icon[fieldtype.value] || "es-line-form");

function toggle(prop, event) {
	event.stopPropagation();
	store.update_field(props.field.fieldname, prop, props.field[prop] ? 0 : 1);
}
</script>

<template>
	<div
		:class="[
			'lb-field-row',
			is_structural ? 'is-structural' : '',
			is_hidden ? 'is-hidden-field' : '',
			is_selected ? 'is-selected' : '',
		]"
		:data-fieldname="field.fieldname"
		@click="store.select(field)"
	>
		<!-- drag handle -->
		<span class="lb-drag-handle" :title="__('Drag to reorder')">
			<span v-html="frappe.utils.icon('es-line-drag', 'xs')" />
		</span>

		<!-- fieldtype icon -->
		<span
			class="lb-field-icon text-muted"
			:title="fieldtype"
			v-html="frappe.utils.icon(icon, 'sm')"
		/>

		<!-- label -->
		<span class="lb-field-label flex-grow-1">
			<span class="field-display-label">{{
				field.label || base.label || field.fieldname
			}}</span>
			<span class="text-muted small ms-1">({{ field.fieldname }})</span>
			<span v-if="is_hidden" class="badge badge-muted ms-1" style="font-size: 0.7em">{{
				__("Hidden")
			}}</span>
			<span v-if="field.reqd" class="badge badge-danger ms-1" style="font-size: 0.7em">{{
				__("Req")
			}}</span>
			<span
				v-if="field.read_only"
				class="badge badge-warning ms-1"
				style="font-size: 0.7em"
				>{{ __("RO") }}</span
			>
		</span>

		<!-- fieldtype badge -->
		<span class="badge badge-secondary lb-field-type">{{ fieldtype }}</span>

		<!-- quick toggles (non-structural only) -->
		<template v-if="!is_structural">
			<label class="lb-toggle" :title="__('Toggle Hidden')" @click.stop>
				<input
					type="checkbox"
					:checked="!!field.hidden"
					@change="toggle('hidden', $event)"
				/>
				{{ __("Hide") }}
			</label>
			<label class="lb-toggle" :title="__('Toggle Required')" @click.stop>
				<input type="checkbox" :checked="!!field.reqd" @change="toggle('reqd', $event)" />
				{{ __("Req") }}
			</label>
			<label class="lb-toggle" :title="__('Toggle Read Only')" @click.stop>
				<input
					type="checkbox"
					:checked="!!field.read_only"
					@change="toggle('read_only', $event)"
				/>
				{{ __("RO") }}
			</label>
		</template>
	</div>
</template>

<style lang="scss" scoped>
.lb-field-row {
	display: flex;
	align-items: center;
	gap: 6px;
	padding: 6px 10px;
	border-bottom: 1px solid var(--border-color);
	background: var(--card-bg);
	cursor: pointer;
	transition: background 0.12s;
	user-select: none;

	&:last-child {
		border-bottom: none;
	}
	&:hover {
		background: var(--control-bg);
	}
	&.is-selected {
		background: var(--blue-50) !important;
		outline: 2px solid var(--blue-300) !important;
		outline-offset: -2px;
	}

	&.is-structural {
		background: var(--subtle-accent);
		font-weight: 600;
		font-size: 0.84em;
		letter-spacing: 0.04em;
		text-transform: uppercase;
	}

	&.is-hidden-field {
		.field-display-label,
		.lb-field-icon {
			opacity: 0.4;
		}
	}
}

.lb-drag-handle {
	cursor: grab;
	color: var(--text-muted);
	flex-shrink: 0;
	padding: 0 2px;
	&:active {
		cursor: grabbing;
	}
}

.lb-field-icon {
	flex-shrink: 0;
}

.lb-field-label {
	font-size: 0.9em;
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.lb-field-type {
	font-size: 0.7em;
	flex-shrink: 0;
}

.lb-toggle {
	display: flex;
	align-items: center;
	gap: 3px;
	font-size: 0.75em;
	color: var(--text-muted);
	margin: 0;
	flex-shrink: 0;
	cursor: pointer;
	white-space: nowrap;

	input {
		margin: 0;
		cursor: pointer;
	}
}
</style>
