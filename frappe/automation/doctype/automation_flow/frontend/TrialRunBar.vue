<!-- The test run's controls: the record to run on, a start button and how the last run went. -->
<template>
	<div class="shrink-0 space-y-3 border-b bg-surface-base px-5 py-3" data-trial-bar>
		<div class="flex items-end gap-2">
			<Link
				v-if="documentType"
				class="w-full max-w-sm"
				:model-value="trial.docname"
				:doctype="documentType"
				:label="__('Record')"
				:placeholder="__('Pick a {0}', [documentType])"
				@update:model-value="trial.pickDocument"
			/>
			<span v-else class="text-p-sm text-ink-gray-6">
				{{ __("This flow has no record. It runs on its own.") }}
			</span>
			<Button v-if="trial.playing" :label="__('Skip')" @click="trial.skip" />
			<Button
				variant="solid"
				icon-left="lucide-play"
				:label="__('Start test run')"
				:loading="trial.running"
				:disabled="!canStart"
				@click="trial.run()"
			/>
		</div>
		<p v-if="!canTest" class="text-p-sm text-ink-gray-6">
			{{ __("Save the flow before testing it.") }}
		</p>
		<p v-if="trial.error" class="text-p-sm text-ink-red-4" role="alert">{{ trial.error }}</p>
		<div aria-live="polite" class="empty:hidden">
			<div
				v-if="trial.summary"
				class="flex items-center gap-2 rounded-6 border bg-surface-gray-1 px-3 py-2"
				data-trial-summary
			>
				<Badge
					:label="trial.playing ? __('Running') : statusLabel(trial.summary.status)"
					:theme="trial.playing ? 'blue' : STATUS_THEMES[trial.summary.status] || 'gray'"
					variant="subtle"
				/>
				<span class="shrink-0 text-p-sm text-ink-gray-6">
					{{ __("{0} of {1} steps ran", [trial.ranCount, trial.stepCount]) }}
				</span>
				<span v-if="trial.summary.error_summary" class="truncate text-p-sm text-ink-red-4">
					{{ trial.summary.error_summary }}
				</span>
				<Button
					v-if="trial.failures.length"
					class="ml-auto shrink-0"
					variant="ghost"
					size="sm"
					:label="trial.detailsOpen ? __('Hide details') : __('Show details')"
					@click="trial.detailsOpen = !trial.detailsOpen"
				/>
			</div>
		</div>
		<div
			v-if="trial.detailsOpen && trial.failures.length"
			class="max-h-40 space-y-2 overflow-y-auto rounded-6 border border-outline-red-2 p-3"
		>
			<div v-for="step in trial.failures" :key="step.step_key" class="space-y-1">
				<div class="text-p-sm font-medium text-ink-gray-8">{{ stepLabel(step) }}</div>
				<div v-if="step.message" class="text-p-xs text-ink-red-4">{{ step.message }}</div>
				<pre v-if="traceOf(step)" class="overflow-x-auto text-p-xs text-ink-gray-6">{{
					traceOf(step)
				}}</pre>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { Badge, Button } from "frappe-ui";
import { __ } from "frappe/i18n";
import { Link } from "@framework/ui/Link";
import { STATUS_THEMES, statusLabel, stepLabel, traceOf } from "./flow/useTrialRun";

const props = defineProps({
	trial: { type: Object, required: true },
	documentType: { type: String, default: "" },
	canTest: Boolean,
});

const canStart = computed(
	() =>
		props.canTest &&
		!props.trial.running &&
		!props.trial.playing &&
		(!props.documentType || !!props.trial.docname)
);
</script>
