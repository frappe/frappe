<template>
	<Icon
		v-if="icon"
		:icon="icon"
		class="automation-canvas-icon size-4 shrink-0"
		:class="toneClass"
	/>
</template>

<script setup lang="ts">
import { computed, type Component } from "vue";
import { Icon } from "frappe-ui";
import type { AutomationCanvasTone } from "./types";

const props = defineProps<{
	icon?: string | Component;
	tone?: AutomationCanvasTone;
}>();

const TONES: Record<AutomationCanvasTone, string> = {
	blue: "text-ink-blue-5",
	green: "text-ink-green-5",
	teal: "text-ink-teal-5",
	amber: "text-ink-amber-5",
	violet: "text-ink-violet-5",
	cyan: "text-ink-cyan-5",
	orange: "text-ink-orange-5",
	pink: "text-ink-pink-5",
	red: "text-ink-red-5",
	gray: "text-ink-gray-6",
	purple: "text-ink-purple-5",
};

const toneClass = computed(() => TONES[props.tone || "gray"]);
</script>

<style scoped>
.automation-canvas-icon {
	stroke-width: 2;
}
</style>
