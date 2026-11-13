<template>
	<div
		class="grid min-h-screen bg-surface-white"
		:class="$slots.preview ? 'lg:grid-cols-2' : ''"
	>
		<section class="flex min-h-screen flex-col px-4 py-5 sm:px-8">
			<header class="flex h-8 items-center justify-between gap-4">
				<slot name="brand" />
				<Button
					v-if="!steps[current]?.required"
					variant="ghost"
					class="-me-2 ms-auto text-ink-gray-6"
					:label="text.skip"
					@click="confirmSkip = true"
				/>
			</header>
			<main class="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-10">
				<div class="flex h-7 items-center justify-between">
					<span class="text-sm text-ink-gray-6">{{ stepOf }}</span>
					<Button
						v-if="backButton && canGoBack"
						variant="ghost"
						size="sm"
						class="-me-2"
						icon-left="lucide-arrow-left"
						:label="text.back"
						@click="back"
					/>
				</div>
				<Progress
					class="mt-2"
					:value="progress"
					:intervals="steps.length"
					size="sm"
					:aria-label="stepOf"
				/>
				<div class="mt-8">
					<slot
						name="step"
						:step="steps[current]"
						:index="current"
						:done="forStep(current).done"
						:skip="forStep(current).skip"
						:back="back"
						:can-go-back="canGoBack"
					/>
				</div>
			</main>
			<slot name="footer" />
		</section>
		<aside
			v-if="$slots.preview"
			class="sticky top-0 hidden h-screen bg-surface-gray-1 lg:block"
		>
			<slot name="preview" :step="steps[current]" />
		</aside>
		<Dialog
			v-model:open="confirmSkip"
			:title="text.skipTitle"
			:message="text.skipMessage"
			size="sm"
			:actions="[
				{ label: text.cancel, onClick: ({ close }) => close() },
				{ label: text.skip, variant: 'solid', onClick: skipAll },
			]"
		/>
	</div>
</template>

<script setup lang="ts">
import { Button, Dialog, Progress } from "frappe-ui";
import { computed, reactive, ref, watch } from "vue";
import { useTelemetry } from "../../telemetry";
import type { SetupFlowLabels, SetupFlowProps, SetupFlowResult } from "./types";

const props = withDefaults(defineProps<SetupFlowProps>(), { backButton: true });
const emit = defineEmits<{ finish: [result: SetupFlowResult] }>();

const defaults: SetupFlowLabels = {
	back: "Back",
	skip: "Skip setup",
	skipTitle: "Skip setup?",
	skipMessage: "You can do all of this later from Settings.",
	cancel: "Cancel",
	stepOf: (step, total) => `Step ${step} of ${total}`,
};
const text = computed(() => ({ ...defaults, ...props.labels }));

const { capture } = useTelemetry();
const current = ref(0);
const confirmSkip = ref(false);
const status = reactive<Record<string, "completed" | "skipped">>({});

const progress = computed(() =>
	props.steps.length ? ((current.value + 1) / props.steps.length) * 100 : 0
);
const stepOf = computed(() => text.value.stepOf(current.value + 1, props.steps.length));

const startedAt = Date.now();
let stepStartedAt = startedAt;
const seconds = (since: number) => Math.round((Date.now() - since) / 1000);

capture("setup_started");
watch(
	current,
	(index) => {
		stepStartedAt = Date.now();
		capture("setup_step_viewed", { step: props.steps[index]?.name });
	},
	{ immediate: true }
);

const canGoBack = computed(() => current.value > 0 && !props.steps[current.value - 1]?.required);

function back() {
	if (!canGoBack.value) return;
	capture("setup_back", { from_step: props.steps[current.value].name });
	skipping = false;
	current.value--;
}

// A second click while the step changes, or after the end, must not move again.
let moving = false;
watch(current, () => (moving = false));

// The slot's actions belong to the step that rendered them: a late or repeated call
// from a step that has already changed does nothing.
function forStep(index: number) {
	return {
		done: (details?: Record<string, unknown>) => {
			if (index === current.value) done(details);
		},
		skip: () => {
			if (index === current.value) skipStep();
		},
	};
}

function done(details: Record<string, unknown> = {}) {
	if (moving) return;
	const step = props.steps[current.value].name;
	status[step] = "completed";
	capture("setup_step_completed", { step, time_on_step_s: seconds(stepStartedAt), ...details });
	advance();
}

function skipStep() {
	if (moving) return;
	const step = props.steps[current.value];
	if (status[step.name] === "completed") return advance();
	if (step.required) return;
	status[step.name] = "skipped";
	capture("setup_step_skipped", { step: step.name, time_on_step_s: seconds(stepStartedAt) });
	advance();
}

let skipping = false;
let skippedFrom = "";
const nextRequired = (after: number) =>
	props.steps.findIndex((s, i) => i > after && s.required && status[s.name] !== "completed");

function advance() {
	moving = true;
	if (skipping) {
		const required = nextRequired(current.value);
		if (required === -1) finish(true);
		else current.value = required;
	} else if (current.value < props.steps.length - 1) current.value++;
	else finish(false);
}

function skipAll({ close }: { close: () => void }) {
	close();
	skipping = true;
	skippedFrom = props.steps[current.value].name;
	advance();
}

function finish(skipped: boolean) {
	if (skipped) capture("setup_skipped", { step: skippedFrom });
	const named = (value: string) => Object.keys(status).filter((s) => status[s] === value);
	const result = { skipped, completed: named("completed"), skippedSteps: named("skipped") };
	capture("setup_finished", {
		skipped,
		duration_s: seconds(startedAt),
		steps_completed: result.completed.length,
	});
	emit("finish", result);
}
</script>
