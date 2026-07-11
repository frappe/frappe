<!-- Icon stepper with completion connectors — frappe-ui TabButtons/Tabs are
     linear tab chrome without per-step icons and completed-state markers. -->
<script setup>
import { inject } from "vue";
import { WIZARD_STEPS, can_go_to_wizard_step } from "../wizard_constants.js";

const props = defineProps({
	current_step: { type: Number, required: true },
});

const emit = defineEmits(["go"]);
const frm = inject("frm");

function can_go_to_step(index) {
	return can_go_to_wizard_step(frm, index, props.current_step);
}

function show_blocked_step_warning(index) {
	if (index === 3) {
		frappe.show_alert({
			message: __("Start the import before opening the Import step."),
			indicator: "orange",
		});
		return;
	}

	frappe.show_alert({
		message: __("Complete the earlier steps before continuing."),
		indicator: "orange",
	});
}

function on_step_click(index) {
	if (!can_go_to_step(index)) {
		show_blocked_step_warning(index);
		return;
	}
	if (index === props.current_step) return;
	// Backward steps skip validation; forward steps validate in the parent handler.
	if (index < props.current_step) {
		emit("go", index);
		return;
	}
	emit("go", index);
}

function step_class(index) {
	return {
		"diw-step": true,
		active: index === props.current_step,
		completed: index < props.current_step,
		"is-locked": !can_go_to_step(index),
	};
}

function step_icon(name) {
	return frappe.utils.icon(name, "sm", "", "", "", true);
}

const check_icon = frappe.utils.icon("check", "xs", "", "", "", true);
</script>

<template>
	<nav class="diw-stepper" :aria-label="__('Import steps')">
		<template v-for="(step, index) in WIZARD_STEPS" :key="step.id">
			<div
				v-if="index > 0"
				class="diw-step-connector"
				:class="{ 'is-completed': index - 1 < current_step }"
			/>
			<button
				type="button"
				:class="step_class(index)"
				:aria-disabled="!can_go_to_step(index)"
				@click="on_step_click(index)"
			>
				<span class="diw-step-marker">
					<span v-if="index < current_step" class="diw-step-check" v-html="check_icon" />
					<span v-else class="diw-step-icon" v-html="step_icon(step.icon)" />
				</span>
				<span class="diw-step-label">{{ step.label }}</span>
			</button>
		</template>
	</nav>
</template>
