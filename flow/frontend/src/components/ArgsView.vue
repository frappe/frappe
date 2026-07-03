<script setup>
import { computed } from "vue";
import { parseArgs } from "@/lib/toolMeta";
import ArgValue from "./ArgValue.vue";

// Entry point for a tool call's arguments: parses once, renders by shape.
const props = defineProps({ arguments: { default: null } });

const parsed = computed(() => parseArgs(props.arguments));
const empty = computed(() => !Object.keys(parsed.value).length);
</script>

<template>
	<ArgValue v-if="!empty" :value="parsed" />
</template>
