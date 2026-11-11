<template>
	<div class="flex h-full min-h-0 flex-col bg-surface-base">
		<div class="flex h-12 shrink-0 items-center gap-1 px-2">
			<Button
				v-if="choosingTrigger"
				variant="ghost"
				icon="lucide-chevron-left"
				:aria-label="__('Back')"
				@click="choosingTrigger = false"
			/>
			<div class="text-base-semibold text-ink-gray-8">{{ title }}</div>
		</div>
		<div class="min-h-0 flex-1 space-y-5 overflow-y-auto p-4">
			<div v-if="loading" class="flex justify-center py-8">
				<LoadingIndicator class="w-4" />
			</div>
			<StepEditor
				v-else-if="selectedStep"
				:step="selectedStep"
				:doc="doc"
				:targets="targets"
			/>
			<TriggerList
				v-else-if="choosingTrigger"
				:sections="triggerSections"
				:model-value="selectedTrigger"
				@update:model-value="pickTrigger"
			/>
			<template v-else>
				<Link
					:model-value="doc.document_type"
					:label="__('DocType')"
					doctype="DocType"
					:filters="docTypeFilters"
					@update:model-value="patch({ document_type: $event })"
				/>
				<div>
					<div class="mb-2 text-base text-ink-gray-5">{{ __("Event") }}</div>
					<button class="block w-full text-left" @click="choosingTrigger = true">
						<ItemListRow
							size="md"
							class="border border-outline-gray-2 hover:bg-surface-gray-2"
						>
							<template v-if="currentTrigger" #prefix>
								<AutomationCanvasIcon :icon="currentTrigger.icon" tone="gray" />
							</template>
							<div class="truncate" :class="{ 'text-ink-gray-4': !currentTrigger }">
								{{ currentTrigger?.label || __("Choose an event") }}
							</div>
							<template #suffix>
								<Icon icon="lucide-chevron-right" class="size-4 text-ink-gray-5" />
							</template>
						</ItemListRow>
					</button>
				</div>
				<TriggerDetails :doc="doc" :fields="fields" :events="events" @update="patch" />
				<WorkflowFilters
					:model-value="doc.filters"
					:doctype="doc.document_type"
					flat
					:info="__('Only start when the record\'s fields match these filters.')"
					@update:model-value="patch({ filters: $event })"
				/>
				<ConditionEditor
					:model-value="doc.condition"
					:doctype="doc.document_type"
					:fields="fields"
					:label="__('Condition')"
					:info="__('Extra check that must also pass; use Expression for Python logic.')"
					variant="outline"
					:placeholder="__('doc.status == \'Open\'')"
					@update:model-value="patch({ condition: $event })"
				/>
				<FormControl
					:model-value="doc.run_as"
					type="select"
					variant="outline"
					:label="__('Run As')"
					:options="runAsOptions"
					@update:model-value="patch({ run_as: $event })"
				/>
				<Link
					v-if="doc.run_as === 'Automation User'"
					:model-value="doc.automation_user"
					:label="__('Automation User')"
					doctype="User"
					@update:model-value="patch({ automation_user: $event })"
				/>
			</template>
		</div>
		<div v-if="canRemove" class="shrink-0 border-t border-outline-gray-2 p-3">
			<Button
				class="w-full"
				variant="subtle"
				theme="red"
				icon-left="lucide-trash-2"
				:label="selectedStep ? __('Delete step') : __('Delete trigger')"
				@click="emit('remove')"
			/>
		</div>
	</div>
</template>

<script setup>
import { __ } from "frappe/i18n";
import { AutomationCanvasIcon } from "@framework/ui/AutomationCanvas";
import { Link } from "@framework/ui/Link";
import ConditionEditor from "./ConditionEditor.vue";
import StepEditor from "./StepEditor.vue";
import TriggerDetails from "./TriggerDetails.vue";
import TriggerList from "./TriggerList.vue";
import WorkflowFilters from "./Filters.vue";
import { capabilitiesFor } from "../flow/workflowCapabilities";
import {
	triggerDefinition,
	triggerFromValue,
	triggerGroups,
	triggerValue,
} from "../flow/workflowTriggers";
import { Button, FormControl, Icon, ItemListRow, LoadingIndicator } from "frappe-ui";
import { computed, ref, watch } from "vue";

const props = defineProps({
	doc: { type: Object, required: true },
	selectedStep: { type: Object, default: null },
	targets: { type: Array, default: () => [] },
	loading: { type: Boolean, default: false },
});

const emit = defineEmits(["update", "remove"]);

const docTypeFilters = { istable: 0 };
const triggerSections = computed(() => triggerGroups(props.doc.document_type));
const selectedTrigger = computed(() => triggerValue(props.doc));
const currentTrigger = computed(() => triggerDefinition(props.doc));

const canRemove = computed(() => (props.selectedStep ? true : Boolean(props.doc.trigger_type)));
const choosingTrigger = ref(false);
watch(
	() => props.selectedStep,
	() => (choosingTrigger.value = false)
);

const title = computed(() => {
	if (props.selectedStep) return __("Step");
	return choosingTrigger.value ? __("Event") : __("Trigger");
});

function pickTrigger(value) {
	patch(triggerFromValue(value));
	choosingTrigger.value = false;
}

/** The builder owns the document; edits here travel back up to it. */
function patch(values) {
	emit("update", values);
}

const runAsOptions = ["Triggering User", "Document Owner", "Automation User"];
const capabilities = computed(() => capabilitiesFor(props.doc.document_type));
const fields = computed(() => capabilities.value?.fields || []);
const events = computed(() => capabilities.value?.custom_events || []);
</script>
