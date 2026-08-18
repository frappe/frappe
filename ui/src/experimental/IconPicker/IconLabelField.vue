<template>
	<div class="space-y-1.5">
		<label class="block text-base text-ink-gray-5">{{ label }}</label>
		<div class="flex items-center gap-2">
			<IconPicker v-model="icon" :sections="sections">
				<template #trigger="{ value }">
					<button
						type="button"
						class="grid size-7 shrink-0 place-content-center rounded bg-surface-gray-2 text-ink-gray-7 transition hover:bg-surface-gray-3 focus-visible:focus-ring"
						aria-label="Change icon"
					>
						<IconGlyph :name="value || 'circle-dashed'" class="size-4" />
					</button>
				</template>
			</IconPicker>
			<FormControl
				class="flex-1"
				v-model="text"
				:placeholder="placeholder"
				autocomplete="off"
				@keydown.enter="emit('submit')"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { FormControl } from "frappe-ui";
import IconGlyph from "./IconGlyph.vue";
import IconPicker from "./IconPicker.vue";
import { useCustomIcons } from "../useCustomIcons";

withDefaults(defineProps<{ label?: string; placeholder?: string }>(), {
	label: "Name",
	placeholder: "",
});

const emit = defineEmits<{ submit: [] }>();

const text = defineModel<string>("text", { default: "" });
const icon = defineModel<string | null>("icon", { default: "" });

const { sections } = useCustomIcons();
</script>
