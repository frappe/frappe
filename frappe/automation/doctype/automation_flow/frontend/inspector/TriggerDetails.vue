<template>
	<div class="space-y-4">
		<template v-if="doc.trigger_type === 'Field Value Changed'">
			<FormControl
				:model-value="doc.trigger_field"
				variant="outline"
				type="select"
				:label="__('Trigger Field')"
				required
				:options="fieldOptions"
				@update:model-value="patch('trigger_field', $event)"
			/>
			<FormControl
				:model-value="doc.from_value"
				variant="outline"
				:label="__('From Value')"
				@update:model-value="patch('from_value', $event)"
			/>
			<FormControl
				:model-value="doc.to_value"
				variant="outline"
				:label="__('To Value')"
				@update:model-value="patch('to_value', $event)"
			/>
		</template>
		<template v-else-if="doc.trigger_type === 'Scheduled'">
			<FormControl
				:model-value="doc.cron_expression"
				variant="outline"
				:label="__('Cron Expression')"
				required
				placeholder="0 9 * * *"
				@update:model-value="patch('cron_expression', $event)"
			/>
		</template>
		<template v-else-if="doc.trigger_type === 'Date Based'">
			<FormControl
				:model-value="doc.date_field"
				variant="outline"
				type="select"
				:label="__('Date Field')"
				required
				:options="dateFieldOptions"
				@update:model-value="patch('date_field', $event)"
			/>
			<FormControl
				:model-value="doc.date_offset"
				variant="outline"
				type="number"
				:label="__('Date Offset')"
				@update:model-value="patch('date_offset', $event)"
			/>
			<FormControl
				:model-value="doc.date_direction"
				variant="outline"
				type="select"
				:label="__('Date Direction')"
				:options="['Before', 'After']"
				@update:model-value="patch('date_direction', $event)"
			/>
		</template>
		<!-- Only for an event the trigger list does not already name. -->
		<template v-else-if="doc.trigger_type === 'Custom Event' && !isNamedEvent">
			<FormControl
				:model-value="doc.custom_event"
				variant="outline"
				type="select"
				:label="__('Custom Event')"
				required
				:options="events"
				@update:model-value="patch('custom_event', $event)"
			/>
		</template>
	</div>
</template>

<script setup>
import { __ } from "frappe/i18n";
import { eventTriggers, triggerValue } from "../flow/workflowTriggers";
import { FormControl } from "frappe-ui";
import { computed } from "vue";

const props = defineProps({
	doc: { type: Object, required: true },
	fields: { type: Array, default: () => [] },
	events: { type: Array, default: () => [] },
});

const emit = defineEmits(["update"]);

/** The builder owns the document, so a changed field travels back up to it. */
function patch(field, value) {
	emit("update", { [field]: value });
}

const isNamedEvent = computed(() =>
	eventTriggers(props.doc.document_type).some(
		(trigger) => trigger.value === triggerValue(props.doc)
	)
);

const fieldOptions = computed(() => {
	return props.fields.map((field) => ({
		label: field.label || field.fieldname,
		value: field.fieldname,
	}));
});

const dateFieldOptions = computed(() => {
	return props.fields
		.filter((field) => ["Date", "Datetime"].includes(field.fieldtype))
		.map((field) => ({
			label: field.label || field.fieldname,
			value: field.fieldname,
		}));
});
</script>
