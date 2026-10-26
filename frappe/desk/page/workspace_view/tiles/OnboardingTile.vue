<script setup>
import { computed, ref } from "vue";
import { Badge, Button, ItemListRow, Progress } from "frappe-ui";
import { ChartCard } from "frappe-ui/charts";
import { get_shell, import_records, run_action, update_step } from "./onboarding.js";

const props = defineProps({
	widget: { type: Object, required: true },
});

const frappe = window.frappe;
const __ = window.__;
const steps = ref(props.widget.steps.map((step) => ({ ...step })));

const is_done = (step) => step.is_complete || step.is_skipped;

// Optional steps show what else the module can do; progress counts the rest.
const required = computed(() => {
	const list = steps.value.filter((step) => !step.is_optional);
	return list.length ? list : steps.value;
});
const completed = computed(() => required.value.filter((step) => step.is_complete).length);
const skipped = computed(
	() => required.value.filter((step) => !step.is_complete && step.is_skipped).length
);
const all_done = computed(() => completed.value + skipped.value === required.value.length);
const progress_label = computed(() =>
	skipped.value
		? __("{0} of {1} done · {2} skipped", [
				completed.value,
				required.value.length,
				skipped.value,
		  ])
		: __("{0} of {1} steps done", [completed.value, required.value.length])
);

const open_step = ref(next_step());

function next_step(after) {
	const start = after ? steps.value.indexOf(after) + 1 : 0;
	const ordered = [...steps.value.slice(start), ...steps.value.slice(0, start)];
	return ordered.find((step) => !is_done(step)) || null;
}

function skip(step) {
	update_step(step, "is_skipped").then(() => (open_step.value = next_step(step)));
}

function step_icon(step) {
	if (step.is_complete) return "lucide-circle-check text-ink-green-3";
	if (step.is_skipped) return "lucide-circle-dashed text-ink-gray-4";
	return "lucide-circle text-ink-gray-4";
}

function module_label(step) {
	const shell = frappe.boot.module_sidebars?.[get_shell(step.module)];
	return __(shell?.label || step.module);
}
</script>

<template>
	<ChartCard>
		<div class="mb-3 flex flex-col gap-1.5">
			<div class="flex items-baseline justify-between gap-3">
				<span class="truncate text-p-base font-medium text-ink-gray-8">
					{{ widget.title }}
				</span>
				<span class="shrink-0 text-p-sm text-ink-gray-5">{{ progress_label }}</span>
			</div>
			<Progress
				size="sm"
				:value="all_done ? 100 : ((completed + skipped) / required.length) * 100"
			/>
		</div>
		<p v-if="all_done" class="text-p-base text-ink-gray-6">{{ __("You're all set up.") }}</p>
		<ul v-else class="-mx-2 flex flex-col gap-0.5">
			<li v-for="step in steps" :key="step.name">
				<ItemListRow
					as="button"
					type="button"
					class="text-left hover:bg-surface-gray-2"
					:active="step === open_step"
					:aria-expanded="step === open_step"
					@click="open_step = step"
				>
					<template #prefix>
						<span :class="step_icon(step)" class="size-4" aria-hidden="true" />
					</template>
					<span class="flex min-w-0 items-center gap-2">
						<span v-if="step.module" class="shrink-0 text-ink-gray-5">
							{{ module_label(step) }}
						</span>
						<span
							class="truncate"
							:class="is_done(step) ? 'text-ink-gray-5' : 'text-ink-gray-8'"
						>
							{{ step.title }}
						</span>
						<Badge v-if="step.is_optional" size="sm" :label="__('Optional')" />
					</span>
					<template v-if="step.is_skipped" #suffix>
						<span class="text-sm text-ink-gray-4">{{ __("Skipped") }}</span>
					</template>
				</ItemListRow>
				<div v-if="step === open_step" class="flex flex-col gap-3 px-2 pb-3 pt-2 ps-8">
					<div
						v-if="step.description"
						class="text-p-sm text-ink-gray-6"
						v-html="frappe.markdown(step.description)"
					/>
					<div class="flex items-center gap-2">
						<Button
							variant="solid"
							icon-right="lucide-arrow-right"
							:label="step.action_label || step.title"
							@click="run_action(step)"
						/>
						<Button
							v-if="step.can_import"
							variant="subtle"
							icon-left="lucide-import"
							:label="__('Import')"
							@click="import_records(step)"
						/>
						<Button
							v-if="!is_done(step)"
							variant="ghost"
							:label="__('Skip')"
							@click="skip(step)"
						/>
					</div>
				</div>
			</li>
		</ul>
	</ChartCard>
</template>
