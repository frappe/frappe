<script setup>
import { ref, onMounted, nextTick, watch } from "vue";
import { __ } from "@/lib/translate";

// Long text clamped to a few lines with a Show more/less toggle when it overflows.
const props = defineProps({ text: { type: String, default: "" } });

const body = ref(null);
const expanded = ref(false);
const overflowing = ref(false);

async function measure() {
	await nextTick();
	const e = body.value;
	if (e) overflowing.value = e.scrollHeight - e.clientHeight > 2;
}
onMounted(measure);
watch(() => props.text, measure);
</script>

<template>
	<div>
		<div
			ref="body"
			class="whitespace-pre-wrap break-words text-sm leading-relaxed text-ink-gray-8"
			:class="expanded ? '' : 'line-clamp-4'"
		>
			{{ text }}
		</div>
		<button
			v-if="overflowing || expanded"
			class="mt-1 text-xs text-ink-gray-5 hover:text-ink-gray-7"
			@click="expanded = !expanded"
		>
			{{ expanded ? __("Show less") : __("Show more") }}
		</button>
	</div>
</template>
