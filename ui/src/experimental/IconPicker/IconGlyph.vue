<template>
	<span v-if="svg" class="inline-block [&>svg]:h-full [&>svg]:w-full" v-html="svg" />
	<Icon v-else :name="glyph" />
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Icon } from "frappe-ui/icons";
import { isCustomIconName, useCustomIcons } from "../useCustomIcons";

const props = withDefaults(
	defineProps<{
		name: string;
		svg?: string;
		fallback?: string;
	}>(),
	{ fallback: "file" }
);

const { svgFor } = useCustomIcons();

const svg = computed(
	() => props.svg ?? (isCustomIconName(props.name) ? svgFor(props.name) : null)
);

const glyph = computed(() => (isCustomIconName(props.name) ? props.fallback : props.name));
</script>
