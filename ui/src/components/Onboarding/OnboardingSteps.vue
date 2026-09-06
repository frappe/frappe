<template>
	<div class="flex flex-col justify-center items-center gap-1 mt-4 mb-7">
		<component :is="logo" class="size-10 shrink-0 rounded mb-4" />
		<div class="text-base font-medium">
			{{ "Welcome to " + title }}
		</div>
		<div class="text-p-base font-normal">
			{{ `${stepsCompleted}/${totalSteps} steps completed` }}
		</div>
	</div>
	<div class="flex flex-col gap-2.5 overflow-hidden">
		<div class="flex justify-between items-center py-0.5">
			<Badge
				:label="`${completedPercentage}% completed`"
				:theme="completedPercentage == 100 ? 'green' : 'orange'"
				size="lg"
			/>
			<div class="flex">
				<Button
					v-if="completedPercentage != 0"
					variant="ghost"
					:label="'Reset all'"
					@click="() => resetAll(afterResetAll)"
				/>
				<Button
					v-if="completedPercentage != 100"
					variant="ghost"
					:label="'Skip all'"
					@click="() => skipAll(afterSkipAll)"
				/>
			</div>
		</div>
		<div class="flex flex-col gap-1.5 overflow-y-auto">
			<div
				v-for="step in steps"
				:key="step.title"
				class="group w-full flex gap-2 justify-between items-center hover:bg-surface-gray-1 rounded px-2 py-1.5 cursor-pointer"
				@click.stop="() => !step.completed && !isDependent(step) && step.onClick?.()"
			>
				<component
					:is="isDependent(step) ? Tooltip : 'div'"
					:text="dependsOnTooltip(step)"
				>
					<div
						class="flex gap-2 items-center"
						:class="[
							step.completed
								? 'text-ink-gray-5'
								: isDependent(step)
								? 'text-ink-gray-4'
								: 'text-ink-gray-8',
						]"
					>
						<component :is="step.icon" class="h-4" />
						<div class="text-base" :class="{ 'line-through': step.completed }">
							{{ step.title }}
						</div>
					</div>
				</component>
				<Button
					v-if="!step.completed && !isDependent(step)"
					:label="'Skip'"
					class="!h-4 text-xs !text-ink-gray-6 hidden group-hover:flex"
					@click="() => skip(step.name, afterSkip)"
				/>
				<Button
					v-else-if="!isDependent(step)"
					:label="'Reset'"
					class="!h-4 text-xs !text-ink-gray-6 hidden group-hover:flex"
					@click.stop="() => reset(step.name, afterReset)"
				/>
			</div>
		</div>
	</div>
</template>
<script setup lang="ts">
import { Badge, Button, Tooltip } from "frappe-ui";
import { useOnboarding } from "./onboarding";
import type { OnboardingStep, OnboardingStepsProps } from "./types";

const props = withDefaults(defineProps<OnboardingStepsProps>(), {
	appName: "frappecrm",
	title: "Frappe CRM",
});

function isDependent(step: OnboardingStep) {
	if (step.dependsOn && !step.completed) {
		const dependsOnStep = steps?.find((s) => s.name === step.dependsOn);
		if (dependsOnStep && !dependsOnStep.completed) {
			return true;
		}
	}
	return false;
}

function dependsOnTooltip(step: OnboardingStep) {
	if (step.dependsOn && !step.completed) {
		const dependsOnStep = steps?.find((s) => s.name === step.dependsOn);
		if (dependsOnStep && !dependsOnStep.completed) {
			return `You need to complete "${dependsOnStep.title}" first.`;
		}
	}
	return "";
}

const { steps, stepsCompleted, totalSteps, completedPercentage, skip, skipAll, reset, resetAll } =
	useOnboarding(props.appName)!;
</script>
