<template>
	<div class="space-y-5">
		<Combobox
			:model-value="step.step_type"
			@update:model-value="setStepType"
			variant="outline"
			side="bottom"
			:label="__('Step Type')"
			:options="stepTypeOptions"
		>
			<template #item-prefix="{ item }">
				<AutomationCanvasIcon :icon="item.icon" />
			</template>
			<template #item-label="{ item }">
				<div class="min-w-0">
					<div class="truncate">{{ item.label }}</div>
					<div v-if="item.description" class="truncate text-p-sm text-ink-gray-5">
						{{ item.description }}
					</div>
				</div>
			</template>
		</Combobox>

		<template v-if="step.step_type === 'If'">
			<ConditionEditor
				v-model="step.step_condition"
				:doctype="doc.document_type"
				:fields="conditionFields"
				variant="outline"
				:label="__('Condition')"
				:placeholder="__('doc.status == \'Qualified\'')"
			/>
		</template>

		<template v-else-if="step.step_type === 'Wait'">
			<div class="flex items-start gap-2">
				<FormControl
					:model-value="params.value"
					type="number"
					variant="outline"
					class="w-24 shrink-0"
					:label="__('Wait')"
					@update:model-value="setParam('value', amount($event))"
				/>
				<FormControl
					:model-value="params.unit || 'Minutes'"
					type="select"
					variant="outline"
					class="min-w-0 flex-1"
					:label="__('Unit')"
					:options="waitUnits"
					@update:model-value="setParam('unit', $event)"
				/>
			</div>
		</template>

		<template v-else-if="step.step_type === 'WaitForEvent'">
			<FormControl
				:model-value="params.event_name"
				type="select"
				variant="outline"
				:label="__('Wait for')"
				:options="eventOptions"
				:placeholder="__('Choose an event')"
				@update:model-value="pickEvent($event)"
			/>
			<FormControl
				v-if="correlationOptions.length"
				:model-value="params.correlation_key"
				type="select"
				variant="outline"
				:label="__('Belonging to')"
				:options="correlationOptions"
				@update:model-value="setParam('correlation_key', $event)"
			/>
			<FormControl
				v-else
				:model-value="params.correlation_key"
				variant="outline"
				:label="__('Belonging to')"
				:placeholder="correlationPlaceholder"
				@update:model-value="setParam('correlation_key', $event)"
			/>
			<div class="flex items-start gap-2">
				<FormControl
					:model-value="params.timeout_value"
					type="number"
					variant="outline"
					class="w-24 shrink-0"
					:label="__('Timeout')"
					@update:model-value="setParam('timeout_value', amount($event))"
				/>
				<FormControl
					:model-value="params.timeout_unit || 'Days'"
					type="select"
					variant="outline"
					class="min-w-0 flex-1"
					:label="__('Unit')"
					:options="waitUnits"
					@update:model-value="setParam('timeout_unit', $event)"
				/>
			</div>
		</template>

		<template v-else>
			<Combobox
				:model-value="step.action_type"
				@update:model-value="setAction"
				variant="outline"
				side="bottom"
				:label="__('Action')"
				:options="actionOptions"
				:placeholder="__('Choose what this step does')"
			>
				<template #item-prefix="{ item }">
					<AutomationCanvasIcon :icon="item.icon" />
				</template>
				<template #item-label="{ item }">
					<div class="min-w-0">
						<div class="truncate">{{ item.label }}</div>
						<div v-if="item.description" class="truncate text-p-sm text-ink-gray-5">
							{{ item.description }}
						</div>
					</div>
				</template>
			</Combobox>
			<TargetPicker
				v-if="targets.length > 1"
				v-model="step.target"
				:targets="targets"
				:label="__('Record')"
			/>
			<ParamEditor
				:action="step"
				:schema="schema"
				:doctype="targetDoctype"
				:fields="fields"
			/>
		</template>

		<ConditionEditor
			v-if="step.step_type !== 'If'"
			v-model="step.step_condition"
			:doctype="doc.document_type"
			:fields="conditionFields"
			variant="outline"
			:label="__('Only run when')"
			:placeholder="__('doc.status == \'Open\'')"
		/>

		<div class="border-t border-outline-gray-2 pt-4">
			<button
				class="flex w-full items-center gap-1 text-sm text-ink-gray-5"
				:aria-expanded="showAdvanced"
				@click="showAdvanced = !showAdvanced"
			>
				<Icon
					icon="lucide-chevron-right"
					class="size-4"
					:class="{ 'rotate-90': showAdvanced }"
				/>
				{{ __("Advanced") }}
			</button>
			<div v-if="showAdvanced" class="mt-4 space-y-5">
				<FormControl
					v-model="step.step_key"
					variant="outline"
					:label="__('Step name')"
					:placeholder="suggestedKey"
					:description="__('Names this step in run logs and in its result path.')"
				/>
				<FormControl
					v-if="schema?.output_schema"
					v-model="step.output_alias"
					variant="outline"
					:label="__('Name the result')"
					:placeholder="__('deal')"
					:description="__('Lets a later step act on what this one produced.')"
				/>
				<div
					v-if="outputPaths.length"
					class="min-w-0 overflow-hidden rounded-4 bg-surface-gray-2 p-3"
				>
					<div class="mb-1 text-xs-semibold text-ink-gray-5">
						{{ __("Available to later steps") }}
					</div>
					<div
						v-for="path in outputPaths"
						:key="path"
						class="break-all font-mono text-xs text-ink-gray-7"
					>
						{{ path }}
					</div>
				</div>
				<ParamEditor
					v-if="showAdvancedParams"
					:action="step"
					:schema="schema"
					:doctype="targetDoctype"
					:fields="fields"
					advanced
				/>
			</div>
		</div>
	</div>
</template>

<script setup>
import { __ } from "frappe/i18n";
import { AutomationCanvasIcon } from "@framework/ui/AutomationCanvas";
import ConditionEditor from "./ConditionEditor.vue";
import ParamEditor from "./ParamEditor.vue";
import TargetPicker from "./TargetPicker.vue";
import { actionIcon, stepTypeIcon } from "../flow/workflowIcons";
import { groupActionsByApp } from "../flow/workflowBlocks";
import { actionSchema, capabilitiesFor, stepParams } from "../flow/workflowCapabilities";
import { defaultStepKey } from "../flow/workflowSteps";
import { Combobox, FormControl, Icon } from "frappe-ui";
import { computed, ref } from "vue";

const props = defineProps({
	step: { type: Object, required: true },
	doc: { type: Object, required: true },
	targets: { type: Array, default: () => [] },
});

const stepTypeOptions = [
	{ label: __("Action"), value: "Action" },
	{ label: __("Wait"), value: "Wait" },
	{ label: __("Wait for event"), value: "WaitForEvent" },
	{ label: __("If / Else"), value: "If" },
].map((option) => ({ ...option, ...stepTypeIcon(option.value) }));

const waitUnits = [
	{ label: __("Seconds"), value: "Seconds" },
	{ label: __("Minutes"), value: "Minutes" },
	{ label: __("Hours"), value: "Hours" },
	{ label: __("Days"), value: "Days" },
];
const correlationPlaceholder = "{{ doc.message_id or doc.name }}";

const step = computed(() => props.step);
const showAdvanced = ref(false);

const params = computed(() => stepParams(step.value));
const suggestedKey = computed(() => defaultStepKey(step.value));

const targetDoctype = computed(
	() =>
		props.targets.find((target) => target.alias === (step.value.target || "trigger"))?.doctype
);

const fields = computed(() => capabilitiesFor(targetDoctype.value)?.fields || []);
// A step condition reads `doc`, which is always the trigger record; only `target` is the step's record.
const conditionFields = computed(() => capabilitiesFor(props.doc.document_type)?.fields || []);

const actionOptions = computed(() =>
	groupActionsByApp(availableActions.value, (action) =>
		actionOption(action.action_type, action.label)
	)
);

// Never render a chosen action as an empty field, even if its DocType is still unknown.
const availableActions = computed(() => {
	const actions = capabilitiesFor(targetDoctype.value)?.actions || [];
	if (!step.value.action_type || actions.some(isChosen)) return actions;
	return [schema.value || { action_type: step.value.action_type }, ...actions];
});

function actionOption(actionType, label) {
	return {
		value: actionType,
		label: label || actionType,
		...actionIcon(actionType),
	};
}

function isChosen(action) {
	return action.action_type === step.value.action_type;
}

const eventOptions = computed(() => capabilitiesFor(props.doc.document_type)?.custom_events || []);

const correlationOptions = computed(() => {
	const event = eventOptions.value.find((option) => option.value === params.value.event_name);
	return event?.correlation_options || [];
});

/** Picking an event brings its default correlation with it, so the step works untouched. */
function pickEvent(name) {
	const event = eventOptions.value.find((option) => option.value === name);
	const suggested = event?.correlation_options?.[0]?.value;
	step.value.params = JSON.stringify(
		{ ...params.value, event_name: name, correlation_key: suggested || "" },
		null,
		2
	);
}

const schema = computed(() => actionSchema(targetDoctype.value, step.value.action_type));

const outputPaths = computed(() => {
	const keys = Object.keys(schema.value?.output_schema || {});
	const key = step.value.step_key || __("<step key>");
	return keys.map((name) => `context.steps.${key}.${name}`);
});

const showAdvancedParams = computed(() => step.value.action_type === "SetFieldValue");

// Params belong to one step or action type; a switch starts from that type's defaults.
const TYPE_DEFAULT_PARAMS = { Wait: { unit: "Minutes" }, WaitForEvent: { timeout_unit: "Days" } };

function setStepType(value) {
	step.value.step_type = value;
	step.value.params = JSON.stringify(TYPE_DEFAULT_PARAMS[value] || {});
}

function setAction(value) {
	step.value.action_type = value;
	step.value.params = "{}";
}

// An emptied box clears the amount instead of saving a wait of zero.
function amount(value) {
	return value === "" || value == null ? null : Number(value);
}

function setParam(name, value) {
	step.value.params = JSON.stringify({ ...params.value, [name]: value }, null, 2);
}
</script>
