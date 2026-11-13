<!-- The DocType's description, light text typed in place under its name. It stages when left. -->
<template>
	<textarea
		v-if="canvas.editable && !canvas.customize"
		ref="input"
		:value="description"
		:placeholder="__('Add a description of what one record holds')"
		rows="1"
		class="mt-2 block w-full resize-none overflow-hidden border-0 bg-transparent p-0 text-base text-ink-gray-6 placeholder:text-ink-gray-4 focus:outline-none focus:ring-0"
		:aria-label="__('Description')"
		data-editor-description
		@input="grow"
		@keydown.enter.exact.prevent="input?.blur()"
		@change="set(($event.target as HTMLTextAreaElement).value)"
	/>
	<p v-else-if="description" class="mt-2 text-base text-ink-gray-6">{{ description }}</p>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";

const props = defineProps<{ canvas: DesignCanvas }>();

const input = ref<HTMLTextAreaElement | null>(null);
const description = computed(() => props.canvas.working.value.description);

watch(description, () => nextTick(grow), { immediate: true });

function grow() {
	const area = input.value;
	if (!area) return;
	area.style.height = "auto";
	area.style.height = `${area.scrollHeight}px`;
}

function set(value: string) {
	const typed = value.trim();
	if (typed === description.value) return;
	void acts.perform("settings.set_doctype_property", { property: "description", value: typed });
}
</script>
