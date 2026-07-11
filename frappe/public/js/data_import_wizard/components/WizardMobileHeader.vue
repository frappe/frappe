<!-- Mobile step chrome: title, step counter, and segmented progress bar. -->
<script setup>
import { computed } from "vue";
import { WIZARD_STEPS } from "../wizard_constants.js";

const props = defineProps({
	current_step: { type: Number, required: true },
});

const step = computed(() => WIZARD_STEPS[props.current_step]);
const step_count = WIZARD_STEPS.length;
</script>

<template>
	<div class="diw-mobile-step-header">
		<div class="diw-mobile-step-heading">
			<h4 class="diw-mobile-step-title">{{ step?.label }}</h4>
			<span class="diw-mobile-step-counter text-muted">
				{{ __("Step {0} of {1}", [current_step + 1, step_count]) }}
			</span>
		</div>
		<div
			class="diw-mobile-progress"
			role="progressbar"
			:aria-valuenow="current_step + 1"
			aria-valuemin="1"
			:aria-valuemax="step_count"
		>
			<div
				v-for="index in step_count"
				:key="index"
				class="diw-mobile-progress-segment"
				:class="{ active: index - 1 <= current_step }"
			/>
		</div>
	</div>
</template>
