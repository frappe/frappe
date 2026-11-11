<template>
	<div class="space-y-4">
		<template v-if="isSetFieldValue && !advanced">
			<div class="space-y-3">
				<div
					v-for="(row, index) in rows"
					:key="index"
					class="space-y-1.5 rounded-4 border border-outline-gray-2 p-2"
				>
					<div class="flex items-center gap-2">
						<Combobox
							class="flex-1"
							variant="outline"
							:model-value="row.field"
							:options="availableFieldOptions(row.field)"
							:placeholder="__('Choose field')"
							:aria-label="__('Field')"
							@update:model-value="setRow(index, 'field', $event)"
						/>
						<Button
							v-if="rows.length > 1"
							variant="ghost"
							size="sm"
							icon="lucide-trash-2"
							:aria-label="__('Remove field')"
							@click="removeRow(index)"
						/>
					</div>
					<Link
						v-if="fieldFor(row)?.fieldtype === 'Link'"
						:model-value="row.value"
						:doctype="fieldFor(row).options"
						:placeholder="__('Choose {0}', [fieldFor(row).options])"
						:aria-label="__('Value')"
						@update:model-value="setRow(index, 'value', $event)"
					/>
					<Combobox
						v-else-if="choicesFor(row).length"
						variant="outline"
						:model-value="row.value"
						:options="choicesFor(row)"
						:placeholder="__('Choose value')"
						:aria-label="__('Value')"
						@update:model-value="setRow(index, 'value', $event)"
					/>
					<FormControl
						v-else
						variant="outline"
						:model-value="row.value"
						:placeholder="__('Value')"
						:aria-label="__('Value')"
						@update:model-value="setRow(index, 'value', $event)"
					/>
					<div v-if="!isPicked(row)" class="flex justify-end">
						<FieldToken :fields="fields" @insert="appendRowToken(index, $event)" />
					</div>
				</div>
				<Button
					variant="ghost"
					size="sm"
					icon-left="lucide-plus"
					:label="__('Add field')"
					:disabled="!rows[rows.length - 1]?.field"
					@click="addRow"
				/>
			</div>
		</template>
		<template v-else-if="isSetFieldValue && advanced">
			<div>
				<div class="mb-1.5 flex items-center gap-1.5">
					<label class="block text-sm text-ink-gray-5">
						{{ __("Field Values") }}
					</label>
					<Tooltip :text="fieldValuesHelp">
						<Icon icon="lucide-circle-help" class="size-3.5 text-ink-gray-5" />
					</Tooltip>
				</div>
				<FormControl
					:model-value="valuesText"
					type="textarea"
					variant="outline"
					:placeholder="fieldValuesPlaceholder"
					:aria-label="__('Field Values')"
					@update:model-value="setValuesText"
				/>
				<div class="mt-1 flex justify-end">
					<FieldToken :fields="fields" @insert="appendValuesToken" />
				</div>
			</div>
		</template>
		<template v-else>
			<template v-for="field in schemaFields" :key="field.fieldname">
				<WorkflowUserPicker
					v-if="field.control === 'users'"
					:model-value="arrayValue(field)"
					:action-type="action.action_type"
					:fieldname="field.fieldname"
					:doctype="doctype"
					:params="action.params"
					:label="field.label"
					:required="Boolean(field.reqd)"
					variant="outline"
					@update:model-value="setParam(field.fieldname, $event)"
				/>
				<div v-else-if="field.fieldtype === 'Link'">
					<FormControl
						v-if="isTemplate(field)"
						:model-value="params[field.fieldname]"
						type="text"
						variant="outline"
						:label="field.label"
						:required="Boolean(field.reqd)"
						:placeholder="__('Clear to pick a record instead')"
						@update:model-value="setParam(field.fieldname, $event)"
					/>
					<Link
						v-else
						:model-value="params[field.fieldname]"
						:doctype="field.options"
						:filters="field.link_filters || {}"
						:label="field.label"
						:required="Boolean(field.reqd)"
						@update:model-value="setParam(field.fieldname, $event)"
					/>
					<div v-if="field.templatable" class="mt-1 flex justify-end">
						<FieldToken :fields="fields" @insert="appendToken(field, $event)" />
					</div>
				</div>
				<FormControl
					v-else-if="field.fieldtype === 'Select'"
					:model-value="params[field.fieldname]"
					type="select"
					variant="outline"
					:label="field.label"
					:required="Boolean(field.reqd)"
					:options="optionsFor(field)"
					@update:model-value="setParam(field.fieldname, $event)"
				/>
				<div v-else>
					<FormControl
						:model-value="valueFor(field)"
						:type="controlType(field)"
						:label="field.label"
						:required="Boolean(field.reqd)"
						variant="outline"
						@update:model-value="setParam(field.fieldname, castValue(field, $event))"
					/>
					<div v-if="acceptsTemplate(field)" class="mt-1 flex justify-end">
						<FieldToken :fields="fields" @insert="appendToken(field, $event)" />
					</div>
				</div>
			</template>
		</template>
	</div>
</template>

<script setup>
import { __ } from "frappe/i18n";
import { Link } from "@framework/ui/Link";
import FieldToken from "./FieldToken.vue";
import WorkflowUserPicker from "./UserPicker.vue";
import { stepParams } from "../flow/workflowCapabilities";
import {
	formatJsonFieldValue,
	isCommittableJson,
	parseJsonFieldInput,
	useFieldRows,
} from "../flow/workflowParams";
import { Button, Combobox, FormControl, Icon, Tooltip } from "frappe-ui";
import { computed, ref, watch } from "vue";

const props = defineProps({
	action: { type: Object, required: true },
	schema: { type: Object, default: null },
	doctype: { type: String, default: "" },
	fields: { type: Array, default: () => [] },
	advanced: { type: Boolean, default: false },
});

const action = computed(() => props.action);
const isSetFieldValue = computed(() => action.value.action_type === "SetFieldValue");
const isIncrement = computed(() => action.value.action_type === "IncrementFieldValue");
const NUMERIC_FIELDTYPES = ["Int", "Float", "Currency", "Percent"];
/**
 * What each param stands in for, from the pairs the schema declares - a linked Server Script
 * and one written by hand, say. Both directions, so either half knows about the other.
 */
const standIns = computed(() => {
	const map = {};
	(props.schema?.params_schema || []).forEach((field) => {
		if (!field.exclusive_with) return;
		(map[field.fieldname] ||= []).push(field.exclusive_with);
		(map[field.exclusive_with] ||= []).push(field.fieldname);
	});
	return map;
});

const schemaFields = computed(() => (props.schema?.params_schema || []).filter(isShown));

/** A param gives way to the one it stands in for while that one is on screen and filled, and
    a param that only applies to one branch of a choice waits for that branch. */
function isShown(field) {
	const givenWay = (standIns.value[field.fieldname] || []).some(
		(other) => isInSchema(other) && isFilled(other)
	);
	return !givenWay && appliesHere(field);
}

function appliesHere(field) {
	return Object.entries(field.visible_when || {}).every(([other, wanted]) => {
		const value = params.value[other];
		return Array.isArray(wanted) ? wanted.includes(value) : value === wanted;
	});
}

function isInSchema(fieldname) {
	return (props.schema?.params_schema || []).some((field) => field.fieldname === fieldname);
}

function isFilled(fieldname) {
	const value = params.value[fieldname];
	return value !== undefined && value !== null && value !== "";
}
const fieldValuesHelp = __(
	"Set more fields at once as JSON. These are applied together with the Field and Value above, in the same save."
);
const fieldValuesPlaceholder = '{\n  "status": "Junk"\n}';

const params = computed(() => stepParams(action.value));

function optionsFor(field) {
	if (field.options_source === "doc_fields") {
		// Incrementing only makes sense on a number, and the run-time validation rejects the rest.
		return isIncrement.value
			? docFieldOptions.value.filter((option) =>
					NUMERIC_FIELDTYPES.includes(option.fieldtype)
			  )
			: docFieldOptions.value;
	}
	return String(field.options || "")
		.split("\n")
		.filter(Boolean);
}

const docFieldOptions = computed(() => {
	return props.fields.map((field) => ({
		label: field.label || field.fieldname,
		value: field.fieldname,
		fieldtype: field.fieldtype,
	}));
});

/**
 * A value is only free text when the field it sets has no vocabulary of its own. Link and
 * Select fields carry theirs in the schema, so offer that instead of a box the user can only
 * get wrong - the run-time validation would reject it anyway.
 */
const { rows, reload, sync, setRow, addRow, removeRow } = useFieldRows(
	() => params.value,
	(next) => {
		action.value.params = JSON.stringify(next, null, 2);
	}
);

// The inspector reuses this editor across steps, so a new step reloads the rows.
watch(() => props.action, reload);
watch(
	() => props.action.params,
	() => {
		sync();
		followValues();
	}
);

const valuesText = ref(formatJsonFieldValue(params.value.values) ?? "");
watch(
	() => props.action,
	() => (valuesText.value = formatJsonFieldValue(params.value.values) ?? "")
);

// The other editor may have changed `values`; half-typed text of this one is left alone.
function followValues() {
	const saved = JSON.stringify(params.value.values ?? "");
	const typed = JSON.stringify(parseJsonFieldInput(valuesText.value));
	if (isCommittableJson(valuesText.value) && typed !== saved) {
		valuesText.value = formatJsonFieldValue(params.value.values) ?? "";
	}
}

function setValuesText(text) {
	valuesText.value = text;
	if (isCommittableJson(text)) setParam("values", parseJsonFieldInput(text));
}

const CHOICE_FIELDTYPES = ["Select", "Check"];

function fieldFor(row) {
	return props.fields.find((field) => field.fieldname === row.field);
}

function choicesFor(row) {
	const field = fieldFor(row);
	if (!field || !CHOICE_FIELDTYPES.includes(field.fieldtype)) return [];
	if (field.fieldtype === "Check") {
		return [
			{ label: __("Yes"), value: "1" },
			{ label: __("No"), value: "0" },
		];
	}
	return String(field.options || "")
		.split("\n")
		.filter(Boolean)
		.map((option) => ({ label: option, value: option }));
}

function isPicked(row) {
	return fieldFor(row)?.fieldtype === "Link" || choicesFor(row).length > 0;
}

// A field already set by another row would silently overwrite it, so it leaves the list.
function availableFieldOptions(current) {
	const taken = rows.value.map((row) => row.field).filter((field) => field !== current);
	return docFieldOptions.value.filter((option) => !taken.includes(option.value));
}

function appendRowToken(index, token) {
	const current = rows.value[index]?.value;
	const text = typeof current === "string" ? current : "";
	setRow(index, "value", `${text}${token}`);
}

function valueFor(field) {
	const value = params.value[field.fieldname];
	if (field.fieldtype === "JSON") return formatJsonFieldValue(value);
	return Array.isArray(value) ? value.join(", ") : value;
}

function arrayValue(field) {
	const value = params.value[field.fieldname];
	if (Array.isArray(value)) return value;
	return value ? [value] : [];
}

function controlType(field) {
	if (["JSON", "Text Editor"].includes(field.fieldtype)) return "textarea";
	if (["Int", "Float", "Currency", "Percent"].includes(field.fieldtype)) return "number";
	return "text";
}

function castValue(field, value) {
	if (field.fieldtype === "JSON") return castJsonField(value);
	if (controlType(field) === "number") return value === "" ? null : Number(value);
	return value;
}

function castJsonField(value) {
	return parseJsonFieldInput(value);
}

const TEMPLATE_FIELDTYPES = ["Data", "Small Text", "Text", "Text Editor", "JSON"];

function acceptsTemplate(field) {
	return TEMPLATE_FIELDTYPES.includes(field.fieldtype);
}

/**
 * A templatable Link holds either a record name or a template, and only one control can show
 * both: the picker offers names that exist, so a template swaps it for a plain box until the
 * box is cleared.
 */
function isTemplate(field) {
	return String(params.value[field.fieldname] || "").includes("{{");
}

function appendToken(field, token) {
	const current = params.value[field.fieldname];
	const text = typeof current === "string" ? current : "";
	setParam(field.fieldname, `${text}${token}`);
}

function appendValuesToken(token) {
	valuesText.value = `${valuesText.value}${token}`;
	setParam("values", valuesText.value);
}

function setParam(fieldname, value) {
	const next = { ...params.value, [fieldname]: value };
	// What a param stands in for goes when it is filled, whether or not this builder shows it:
	// a flow carrying a written script takes a linked one without the save being rejected.
	if (value) (standIns.value[fieldname] || []).forEach((other) => delete next[other]);
	action.value.params = JSON.stringify(next, null, 2);
}
</script>
