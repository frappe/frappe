<!-- The DocType's description, light text typed in place under its name. It stages when left.
     Customize does not set it, so there it reads with the reason. -->
<template>
	<textarea
		v-if="editable"
		ref="input"
		:value="description"
		:placeholder="holds"
		rows="1"
		class="mt-2 block w-full resize-none overflow-hidden border-0 bg-transparent p-0 text-base text-ink-gray-6 placeholder:text-ink-gray-4 focus:outline-none focus:ring-0"
		:aria-label="__('Description')"
		data-editor-description
		@input="grow"
		@keydown.enter.exact.prevent="input?.blur()"
		@change="set(($event.target as HTMLTextAreaElement).value)"
	/>
	<Tooltip v-else-if="description" :text="reason">
		<p class="mt-2 text-base text-ink-gray-6">{{ description }}</p>
	</Tooltip>
</template>

<script setup lang="ts">
import { Tooltip } from "frappe-ui";
import { computed, nextTick, ref, watch } from "vue";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import { settable } from "./settingsModel";

const props = defineProps<{ canvas: DesignCanvas }>();

const holds = computed(() =>
	props.canvas.state.definition.istable
		? __("Add a description of what one row holds")
		: __("Add a description of what one record holds")
);
const input = ref<HTMLTextAreaElement | null>(null);
const description = computed(
	() => (props.canvas.working.value.settings.properties.description as string) ?? ""
);
const settableHere = computed(() => settable(props.canvas.working.value.settings, "description"));
const editable = computed(() => props.canvas.editable && settableHere.value);
const reason = computed(() =>
	settableHere.value
		? ""
		: __("Only {0}'s DocType sets this. Customize cannot change it.", [
				props.canvas.state.app_title || __("the app"),
		  ])
);

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
