<script setup>
import { ref, computed } from "vue";
import { formatScalar } from "@/lib/toolMeta";
import { __ } from "@/lib/translate";

// A scalar list as wrapping tags, capped behind "+N more" so a huge list can't
// blow up the panel.
const props = defineProps({ items: { type: Array, required: true } });

const LIMIT = 24;
const showAll = ref(false);
const visible = computed(() => (showAll.value ? props.items : props.items.slice(0, LIMIT)));
</script>

<template>
	<div class="flex flex-wrap items-center gap-1.5">
		<span
			v-for="(item, i) in visible"
			:key="i"
			class="rounded-md bg-surface-gray-2 px-2.5 py-1 text-xs text-ink-gray-8"
		>
			{{ formatScalar(item) }}
		</span>
		<button
			v-if="items.length > LIMIT"
			class="text-xs text-ink-gray-5 hover:text-ink-gray-7"
			@click="showAll = !showAll"
		>
			{{ showAll ? __("Show less") : __("+{0} more", [items.length - LIMIT]) }}
		</button>
	</div>
</template>
