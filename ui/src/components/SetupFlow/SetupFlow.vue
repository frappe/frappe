<template>
	<div class="grid min-h-screen bg-surface-base" :class="$slots.preview ? 'lg:grid-cols-2' : ''">
		<!-- From lg up the column is the screen's height and only the step scrolls, so a step
		that grows (a question opening under a list) never moves the header or the footer. -->
		<section class="flex min-h-screen flex-col px-4 py-5 sm:px-8 lg:h-screen">
			<header class="flex h-8 items-center justify-between gap-4">
				<slot name="brand" />
				<div
					class="ms-auto flex items-center gap-1"
					:class="themeToggle ? '-me-1.5' : '-me-2'"
				>
					<Button
						v-if="!steps[current]?.required"
						variant="ghost"
						class="text-ink-gray-6"
						:label="text.skip"
						@click="confirmSkip = true"
					/>
					<Button
						v-if="themeToggle"
						variant="ghost"
						class="text-ink-gray-6"
						:icon="isDark ? 'lucide-sun' : 'lucide-moon'"
						:tooltip="themeLabel"
						:aria-label="themeLabel"
						@click="toggleColorScheme"
					/>
					<slot name="actions" />
				</div>
			</header>
			<div
				data-slot="setup-flow-scroll"
				class="flex flex-1 flex-col lg:min-h-0 lg:overflow-y-auto"
			>
				<main class="mx-auto flex w-full max-w-md flex-1 flex-col pb-10 pt-[12vh]">
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
							:handle-back="forStep(current).handleBack"
						/>
					</div>
				</main>
			</div>
			<slot name="footer" />
		</section>
		<aside
			v-if="$slots.preview"
			class="sticky top-0 hidden h-screen bg-surface-gray-1 lg:block"
			:class="previewSide === 'start' && 'lg:order-first'"
		>
			<slot name="preview" :step="steps[current]" :index="current" :side="previewSide" />
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
import { Button, Dialog, Progress, useColorScheme } from "frappe-ui";
import { computed, reactive, ref, watch } from "vue";
import { useTelemetry } from "../../telemetry";
import type { SetupFlowLabels, SetupFlowProps, SetupFlowResult, StepBack } from "./types";

const props = withDefaults(defineProps<SetupFlowProps>(), {
	backButton: true,
	previewSide: "end",
	themeToggle: true,
});
const emit = defineEmits<{ finish: [result: SetupFlowResult] }>();
/** The step on screen, by name. A name passed in opens that step first, say after a sign-in
 * redirect brings the user back mid-setup; a name set later moves to that step. */
const stepName = defineModel<string>("step");

const defaults: SetupFlowLabels = {
	back: "Back",
	skip: "Skip setup",
	skipTitle: "Skip setup?",
	skipMessage: "You can do all of this later from Settings.",
	cancel: "Cancel",
	darkMode: "Switch to dark mode",
	lightMode: "Switch to light mode",
	stepOf: (step, total) => `Step ${step} of ${total}`,
};
const text = computed(() => ({ ...defaults, ...props.labels }));

const { capture, isEnabled } = useTelemetry();
const { resolvedColorScheme, toggleColorScheme } = useColorScheme();
const isDark = computed(() => resolvedColorScheme.value === "dark");
const themeLabel = computed(() => (isDark.value ? text.value.lightMode : text.value.darkMode));
const opened = props.steps.findIndex((s) => s.name === stepName.value);
const current = ref(opened > -1 ? opened : 0);
watch(current, (index) => (stepName.value = props.steps[index]?.name), { immediate: true });
// A step can send the owner to another one, like back to email when invites cannot go out.
watch(stepName, (name) => {
	const index = props.steps.findIndex((s) => s.name === name);
	if (index > -1) current.value = index;
});
const confirmSkip = ref(false);
const status = reactive<Record<string, "completed" | "skipped">>({});

const progress = computed(() =>
	props.steps.length ? ((current.value + 1) / props.steps.length) * 100 : 0
);
const stepOf = computed(() => text.value.stepOf(current.value + 1, props.steps.length));

const startedAt = Date.now();
let stepStartedAt = startedAt;
const seconds = (since: number) => Math.round((Date.now() - since) / 1000);

// Telemetry loads after the page starts and drops events sent before it is on, so the first
// ones wait for it.
function whenTelemetryOn(send: () => void) {
	if (!isEnabled || isEnabled.value) return send();
	const stop = watch(isEnabled, (on) => {
		if (!on) return;
		stop();
		send();
	});
}
const viewed = (index: number) => capture("setup_step_viewed", { step: props.steps[index]?.name });
whenTelemetryOn(() => {
	capture("setup_started");
	viewed(current.value);
});
watch(current, (index) => {
	stepStartedAt = Date.now();
	viewed(index);
});

const stepBack = ref<StepBack | null>(null);
watch(current, () => (stepBack.value = null));
const stepCanGoBack = computed(() => stepBack.value?.canGoBack() ?? false);
const canGoBack = computed(
	() => stepCanGoBack.value || (current.value > 0 && !props.steps[current.value - 1]?.required)
);

function back() {
	if (stepCanGoBack.value) {
		capture("setup_back", { from_step: props.steps[current.value].name, within_step: true });
		stepBack.value!.back();
		return;
	}
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
		handleBack: (handler: StepBack | null) => {
			if (index === current.value) stepBack.value = handler;
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
