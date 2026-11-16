<template>
	<div>
		<TextInput
			:modelValue="draft"
			:label="field.label"
			:description="field.description"
			:placeholder="field.readOnly ? '' : field.placeholder || __('Choose a color')"
			:required="field.reqd"
			:error="error"
			:disabled="field.readOnly"
			@update:modelValue="onInput"
			@change="(e: Event) => commitTyped(e.target as HTMLInputElement)"
			@keydown="onKeydown"
			@blur="endEdit"
		>
			<template #prefix>
				<span
					v-if="field.readOnly"
					data-slot="swatch"
					class="block size-3.5 rounded-full"
					:class="swatchClass"
					:style="swatchStyle"
				/>
				<span v-else ref="spacer" class="block size-3.5" aria-hidden="true" />
			</template>
		</TextInput>
		<!-- After the input in the DOM, so Tab, autofocus and the grid reach the hex box first. -->
		<Teleport v-if="trigger" :to="trigger.row">
			<div :class="trigger.slotClass">
				<Popover v-model:open="open" :reference="trigger.row">
					<template #trigger>
						<button
							type="button"
							data-slot="swatch"
							:aria-label="__('Pick a color')"
							class="block size-3.5 rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
							:class="swatchClass"
							:style="swatchStyle"
						/>
					</template>
					<ColorPicker :modelValue="modelValue" @pick="commitPicked" />
				</Popover>
			</div>
		</Teleport>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Popover, TextInput } from "frappe-ui";
import ColorPicker from "./ColorPicker.vue";
import { normalizeHex } from "./colorHex";
import { translate as __ } from "../../utils/translate";
import type { FieldComponentEmits, FieldComponentProps } from "./types";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const draft = ref(props.modelValue ?? "");
const open = ref(false);
const spacer = ref<HTMLElement | null>(null);
let edit: { from: string; revertTo: string } | undefined;
let emitted: string | undefined;

watch(
	() => props.modelValue,
	(value) => {
		if (!edit) draft.value = value ?? "";
		else if (value !== emitted) edit = { from: value ?? "", revertTo: value ?? "" };
	}
);

watch(
	() => props.field.readOnly,
	() => endEdit()
);

// TextInput rebuilds its input row when the error or label changes, so follow the spacer.
const trigger = computed(() => {
	const slot = spacer.value?.parentElement;
	return slot?.parentElement
		? { row: slot.parentElement, slotClass: slot.className }
		: undefined;
});

const shown = computed(() => normalizeHex(props.modelValue ?? ""));
const swatchStyle = computed(() => (shown.value ? { backgroundColor: shown.value } : {}));
const swatchClass = computed(() =>
	shown.value ? "border border-outline-gray-2" : "border border-dashed border-outline-gray-3"
);

function parse(text: string): string | null {
	return text.trim() === "" ? "" : normalizeHex(text);
}

function sameColor(a: string | null | undefined, b: string | null | undefined): boolean {
	return (parse(a ?? "") ?? a) === (parse(b ?? "") ?? b);
}

// Ctrl+S saves before blur, so a full hex reaches the record as it is typed;
// `#rgb` waits for change, as typing `#rrggbb` passes through it.
function onInput(text: string) {
	if (text === draft.value) return;
	draft.value = text;
	edit ??= { from: props.modelValue ?? "", revertTo: props.modelValue ?? "" };
	const live = /^#?[0-9a-f]{6}$/i.test(text.trim()) || text.trim() === "";
	setValue((live ? parse(text) : null) ?? edit.revertTo);
}

function commitTyped(input: HTMLInputElement) {
	const { from, revertTo } = edit ?? {
		from: props.modelValue ?? "",
		revertTo: props.modelValue ?? "",
	};
	edit = undefined;
	emitted = undefined;
	const hex = parse(input.value);
	draft.value = input.value = hex ?? revertTo;
	setValue(hex ?? revertTo);
	if (hex !== null && !sameColor(hex, from)) emit("change", hex);
}

// A save keeps the typed hex, so a later bad hex goes back to it.
function onKeydown(e: KeyboardEvent) {
	if (edit && (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s")
		edit.revertTo = props.modelValue ?? "";
}

function endEdit() {
	edit = undefined;
	emitted = undefined;
	draft.value = props.modelValue ?? "";
}

function commitPicked(hex: string) {
	open.value = false;
	edit = undefined;
	draft.value = hex;
	if (sameColor(hex, props.modelValue)) return;
	setValue(hex);
	emit("change", hex);
}

function setValue(value: string) {
	if (sameColor(value, props.modelValue)) return;
	emitted = value;
	emit("update:modelValue", value);
}
</script>
