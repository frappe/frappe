<template>
	<!-- A panel row has no edit state: the row is the trigger, the picker opens below it and
	     the value saves when it closes. × sits at the right edge like Attach's, on editable
	     rows with a value, and shows on hover and focus. -->
	<div ref="rowEl" class="group flex h-7 w-full min-w-0 items-center">
		<Popover v-model:open="open">
			<template #trigger>
				<button
					type="button"
					data-slot="control"
					class="flex h-full min-w-0 flex-1 items-center gap-2 ps-2 pe-2 text-start text-base focus:outline-none"
					:class="field.readOnly ? 'cursor-default' : 'cursor-pointer'"
					:disabled="field.readOnly"
					:aria-label="field.label"
					:aria-invalid="error?.length ? true : undefined"
				>
					<ColorSwatch :field="field" :value="modelValue" />
					<span
						class="truncate"
						:class="modelValue ? 'text-ink-gray-8' : 'text-ink-gray-4'"
					>
						{{ modelValue || field.placeholder }}
					</span>
				</button>
			</template>
			<ColorPicker hexInput :modelValue="modelValue" @pick="pick" @adjust="setValue" />
		</Popover>
		<span
			v-if="modelValue && !field.readOnly"
			class="flex shrink-0 items-center pe-2 opacity-0 focus-within:opacity-100 group-focus-within:opacity-100 group-hover:opacity-100"
		>
			<button
				type="button"
				data-slot="clear"
				:aria-label="__('Clear')"
				:title="__('Clear')"
				class="grid size-4 place-items-center rounded-1 text-ink-gray-5 hover:text-ink-gray-7 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
				@click="clear"
			>
				<span class="lucide-x size-3.5" />
			</button>
		</span>
	</div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import { Popover } from "frappe-ui";
import ColorPicker from "./ColorPicker.vue";
import ColorSwatch from "./ColorSwatch.vue";
import { sameColor } from "./colorHex";
import { translate as __ } from "../../utils/translate";
import type { FieldComponentEmits, FieldComponentProps } from "./types";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const open = ref(false);
const rowEl = ref<HTMLElement | null>(null);
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

// One click empties the row and saves at once; no picker opens.
function clear() {
	const hadFocus = rowEl.value?.contains(document.activeElement);
	emit("update:modelValue", "");
	emit("change", "");
	if (hadFocus) {
		nextTick(() => rowEl.value?.querySelector<HTMLElement>("[data-slot=control]")?.focus());
	}
}

function pick(hex: string) {
	setValue(hex);
	open.value = false;
}
</script>
