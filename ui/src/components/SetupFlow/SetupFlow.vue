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
						v-if="current > 0 && !steps[current - 1]?.required"
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
						:done="done"
						:skip="skipStep"
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

const props = defineProps<SetupFlowProps>();
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

function back() {
	capture("setup_back", { from_step: props.steps[current.value].name });
	current.value--;
}

function done(details: Record<string, unknown> = {}) {
	const step = props.steps[current.value].name;
	status[step] = "completed";
	capture("setup_step_completed", { step, time_on_step_s: seconds(stepStartedAt), ...details });
	advance();
}

function skipStep() {
	const step = props.steps[current.value].name;
	if (status[step] !== "completed") status[step] = "skipped";
	capture("setup_step_skipped", { step, time_on_step_s: seconds(stepStartedAt) });
	advance();
}

function advance() {
	if (current.value < props.steps.length - 1) current.value++;
	else finish(false);
}

function skipAll({ close }: { close: () => void }) {
	close();
	capture("setup_skipped", { step: props.steps[current.value].name });
	finish(true);
}

function finish(skipped: boolean) {
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
