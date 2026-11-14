<!-- "Add field" in a section: a popover below the button takes the label and guesses the type from
     its words; Enter adds and keeps it open, Done closes it. -->
<template>
	<Popover v-model:open="open" side="bottom" align="start" :auto-focus="false">
		<template #trigger>
			<div class="flex w-fit" data-canvas-add-field @click.stop>
				<Button
					variant="subtle"
					size="sm"
					icon-left="lucide-plus"
					:label="__('Add field')"
					:class="{ '!bg-surface-gray-3': open }"
				/>
			</div>
		</template>
		<form
			ref="form"
			class="flex w-[320px] flex-col gap-2 p-2"
			data-canvas-add-row
			@submit.prevent="add"
			@click.stop
		>
			<TextInput
				v-model="label"
				:placeholder="__('Field label, like Due date')"
				autocomplete="off"
			/>
			<div class="flex items-center gap-2">
				<Dropdown :options="menu" side="bottom" align="start">
					<Button
						size="sm"
						variant="subtle"
						:icon-left="typeIcon(type)"
						icon-right="lucide-chevron-down"
						:label="chip"
						data-canvas-guessed-type
					/>
				</Dropdown>
				<span class="min-w-0 flex-1 truncate text-sm text-ink-gray-5">{{ hint }}</span>
			</div>
			<div class="flex justify-end gap-1.5 border-t border-outline-gray-1 pt-2">
				<Button size="sm" variant="ghost" :label="__('Done')" @click="open = false" />
				<Button
					size="sm"
					variant="subtle"
					type="submit"
					:label="__('Add')"
					:disabled="!label.trim()"
				/>
			</div>
		</form>
	</Popover>
</template>

<script setup lang="ts">
import { computed, inject, nextTick, ref, watch } from "vue";
import { Button, Dropdown, Popover, TextInput } from "frappe-ui";
import { acts } from "@/acts/dispatcher";
import type { Addresses } from "@/addresses";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import { typeMenuOptions } from "./fieldPanel";
import { guessFieldtype } from "./fieldRules";
import { typeIcon, typeName, typeOf } from "./fieldtypes";

const props = defineProps<{ canvas: DesignCanvas; section: string }>();

const form = ref<HTMLFormElement | null>(null);
const label = ref("");
// The label drives the type until one is picked on the chip.
const picked = ref<string | null>(null);
const doctypes = inject<Addresses>("addresses")!.doctypes();
const guess = computed(() => guessFieldtype(label.value, doctypes));
const type = computed(() => picked.value ?? typeName(guess.value.fieldtype, guess.value.options));
const chip = computed(() => {
	const options = picked.value || type.value === "Email" ? "" : guess.value.options;
	return options ? `${__(type.value)} · ${__(options)}` : __(type.value);
});
const menu = computed(() => typeMenuOptions(props.canvas, "", pick));
const NEEDS_OPTIONS = ["Link", "Dynamic Link", "Table", "Table MultiSelect", "Select"];
const hint = computed(() => {
	if (picked.value)
		return NEEDS_OPTIONS.includes(picked.value) ? __("Set its options in the panel") : "";
	if (!label.value.trim()) return __("Guessed from the label");
	return guess.value.because
		? __("Guessed from '{0}'", [guess.value.because])
		: __("No guess, so Data");
});
const open = computed({
	get: () => props.canvas.adding.value === props.section,
	set: (value) => {
		if (value) props.canvas.adding.value = props.section;
		else if (props.canvas.adding.value === props.section) props.canvas.adding.value = null;
	},
});

watch(
	open,
	async (opened) => {
		if (!opened) return;
		label.value = "";
		picked.value = null;
		await nextTick();
		setTimeout(focusLabel, 30);
	},
	{ immediate: true }
);

// The type menu hands focus back to the chip as it closes; the label takes it back after.
function pick(name: string) {
	picked.value = name;
	setTimeout(focusLabel, 50);
}

function focusLabel() {
	form.value?.querySelector("input")?.focus({ preventScroll: true });
}

async function add() {
	const typed = label.value.trim();
	if (!typed) return;
	const { fieldtype, options } = picked.value
		? typeOf(picked.value)
		: { fieldtype: guess.value.fieldtype, options: guess.value.options };
	const count = props.canvas.working.value.fields.length;
	await acts.perform("fields.add_field", {
		label: typed,
		fieldtype,
		...(options ? { options } : {}),
		...props.canvas.addPlace(props.section),
	});
	if (props.canvas.working.value.fields.length <= count) return;
	label.value = "";
	picked.value = null;
	focusLabel();
}
</script>
