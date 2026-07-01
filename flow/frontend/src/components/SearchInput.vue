<script setup>
import { ref, onMounted, nextTick } from "vue";
import { FeatherIcon } from "@/lib/ui";

// Shared search field: a search icon, the input, and a #trailing slot for actions.
const props = defineProps({
	modelValue: { type: String, default: "" },
	placeholder: { type: String, default: "" },
	autofocus: { type: Boolean, default: false },
});
defineEmits(["update:modelValue"]);

const input = ref(null);
onMounted(() => props.autofocus && nextTick(() => input.value?.focus()));
</script>

<template>
	<div class="flex items-center gap-1 border-b border-outline-gray-1 py-1 pl-3 pr-2">
		<FeatherIcon name="search" class="h-3.5 w-3.5 shrink-0 text-ink-gray-5" />
		<input
			ref="input"
			:value="modelValue"
			:placeholder="placeholder"
			class="min-w-0 flex-1 border-0 bg-transparent text-sm text-ink-gray-8 outline-none focus:shadow-none focus:outline-none focus:ring-0 placeholder:text-ink-gray-4"
			@input="$emit('update:modelValue', $event.target.value)"
		/>
		<slot name="trailing" />
	</div>
</template>
