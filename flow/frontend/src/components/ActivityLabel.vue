<script setup>
import { nextTick, onMounted, ref, watch } from "vue";

// Live label: cross-fades on text change, shimmers while active, animates its width
// so a trailing chevron glides. Adapted from frappe/flow#9.
const props = defineProps({
	text: { type: String, default: "" },
	active: { type: Boolean, default: false },
});

const sizer = ref(null);
const width = ref("auto");

async function measure() {
	await nextTick();
	if (sizer.value) width.value = `${Math.ceil(sizer.value.getBoundingClientRect().width)}px`;
}

watch(() => props.text, measure);
onMounted(measure);
</script>

<template>
	<span
		class="flow-label relative inline-grid items-center overflow-hidden align-bottom"
		:style="{ width }"
	>
		<span
			ref="sizer"
			class="invisible col-start-1 row-start-1 w-fit justify-self-start whitespace-nowrap"
			aria-hidden="true"
			>{{ text }}</span
		>
		<Transition name="flow-label">
			<span
				:key="text"
				class="col-start-1 row-start-1 whitespace-nowrap"
				:class="active ? 'flow-shimmer-text' : ''"
				>{{ text }}</span
			>
		</Transition>
	</span>
</template>

<style scoped>
.flow-label {
	transition: width 0.25s ease;
}
.flow-label-enter-active,
.flow-label-leave-active {
	transition: opacity 0.25s ease;
}
/* Leaving label goes absolute so it never affects the measured/flow width. */
.flow-label-leave-active {
	position: absolute;
	left: 0;
	top: 0;
}
.flow-label-enter-from,
.flow-label-leave-to {
	opacity: 0;
}
@media (prefers-reduced-motion: reduce) {
	.flow-label,
	.flow-label-enter-active,
	.flow-label-leave-active {
		transition: none;
	}
}
</style>
