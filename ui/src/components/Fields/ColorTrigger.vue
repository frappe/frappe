<template>
	<!-- A panel row has no edit state: the row is the trigger, the picker opens below it and
	     the value saves when it closes. -->
	<Popover v-model:open="open">
		<template #trigger>
			<button
				type="button"
				data-slot="control"
				class="flex h-7 w-full min-w-0 items-center gap-2 px-2 text-start text-base focus:outline-none"
				:class="field.readOnly ? 'cursor-default' : 'cursor-pointer'"
				:disabled="field.readOnly"
				:aria-label="field.label"
				:aria-invalid="error?.length ? true : undefined"
			>
				<ColorSwatch :field="field" :value="modelValue" />
				<span class="truncate" :class="modelValue ? 'text-ink-gray-8' : 'text-ink-gray-4'">
					{{ modelValue || field.placeholder }}
				</span>
			</button>
		</template>
		<ColorPicker hexInput :modelValue="modelValue" @pick="pick" @adjust="setValue" />
	</Popover>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from "vue";
import { Popover } from "frappe-ui";
import ColorPicker from "./ColorPicker.vue";
import ColorSwatch from "./ColorSwatch.vue";
import { sameColor } from "./colorHex";
import type { FieldComponentEmits, FieldComponentProps } from "./types";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const open = ref(false);
let opened = "";

// Every move writes the draft; the one change goes out on close, however it closed. Esc puts
// the opening value back first, so it closes with nothing to save.
watch(open, (isOpen) => {
	if (isOpen) {
		opened = props.modelValue ?? "";
		document.addEventListener("keydown", cancelOnEscape, true);
	} else {
		document.removeEventListener("keydown", cancelOnEscape, true);
		if (!sameColor(props.modelValue, opened)) emit("change", props.modelValue ?? "");
	}
});
onBeforeUnmount(() => document.removeEventListener("keydown", cancelOnEscape, true));

function cancelOnEscape(event: KeyboardEvent) {
	if (event.key === "Escape") setValue(opened);
}

function setValue(hex: string) {
	if (!sameColor(hex, props.modelValue)) emit("update:modelValue", hex);
}

function pick(hex: string) {
	setValue(hex);
	open.value = false;
}
</script>
