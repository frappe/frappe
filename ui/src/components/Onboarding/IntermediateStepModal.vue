<template>
	<Dialog v-model="show" :title="title" :size="size" :actions="actions">
		<!-- body-header retained for backward compat; the new Dialog has no
		body-header slot, so it renders above the body in the default slot. -->
		<slot name="body-header"></slot>
		<slot>
			<div class="flex flex-col gap-2 text-ink-gray-9 text-base">
				<div v-if="currentStep.message">{{ currentStep.message }}</div>
				<video
					v-if="currentStep.videoURL"
					class="w-full rounded-4"
					controls
					autoplay
					muted
				>
					<source :src="currentStep.videoURL" type="video/mp4" />
					Your browser does not support the video tag.
				</video>
			</div>
		</slot>
		<!-- Only forward when provided, else Dialog would render an empty
		actions row instead of the buttons derived from `actions`. -->
		<template v-if="$slots.actions" #actions="slotProps">
			<slot name="actions" v-bind="slotProps"></slot>
		</template>
	</Dialog>
</template>
<script setup lang="ts">
import { Dialog } from "frappe-ui";
import { computed } from "vue";
import type { IntermediateStepModalProps } from "./types";

const props = withDefaults(defineProps<IntermediateStepModalProps>(), {
	// A factory, unlike the object literal the options API version passed —
	// that shared one object across every instance.
	currentStep: () => ({
		title: "Title",
		message: "Message",
		videoURL: "",
		buttonLabel: "Button Label",
		onClick: () => {},
	}),
	dialogOptions: () => ({}),
});

const show = defineModel<boolean>();

// Dialog dropped its `options` prop in favour of `title`/`size`/`actions`.
// dialogOptions still overrides the values derived from currentStep.
const title = computed(() => props.dialogOptions.title ?? props.currentStep.title);

const size = computed(() => props.dialogOptions.size ?? "2xl");

const actions = computed(() => {
	if (props.dialogOptions.actions) return props.dialogOptions.actions;

	return [
		{
			label: props.currentStep.buttonLabel,
			variant: "solid",
			onClick: props.currentStep.onClick,
		},
	];
});
</script>
