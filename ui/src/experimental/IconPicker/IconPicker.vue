<script setup lang="ts">
import {
	ComboboxAnchor,
	ComboboxContent,
	ComboboxEmpty,
	ComboboxInput,
	ComboboxPortal,
	ComboboxRoot,
	ComboboxTrigger,
	ComboboxViewport,
} from "reka-ui";
import { computed, nextTick, onMounted, ref, useSlots, watch } from "vue";
import { Icon } from "frappe-ui/icons";
import IconGlyph from "./IconGlyph.vue";

export interface IconPickerOption {
	value: string;
	label?: string;
	svg?: string;
}

export interface IconPickerSection {
	label?: string;
	options: IconPickerOption[];
}

export interface IconPickerProps {
	variant?: "subtle" | "outline" | "ghost";
	modelValue?: string | null;
	placeholder?: string;
	disabled?: boolean;
	openOnFocus?: boolean;
	openOnClick?: boolean;
	placement?: "start" | "center" | "end";
	maxIcons?: number;
	sections?: IconPickerSection[];
	lucideSectionLabel?: string;
}

const props = withDefaults(defineProps<IconPickerProps>(), {
	variant: "subtle",
	openOnClick: true,
	openOnFocus: true,
	maxIcons: 100,
	sections: () => [],
	lucideSectionLabel: "Lucide",
});

const emit = defineEmits(["update:modelValue", "focus", "blur", "input"]);

const slots = useSlots();
const hasTrigger = computed(() => !!slots.trigger);

const optionsByValue = computed(() => {
	const map = new Map<string, IconPickerOption>();
	for (const section of props.sections) {
		for (const option of section.options) map.set(option.value, option);
	}
	return map;
});

function getLabel(name: string) {
	const label = optionsByValue.value.get(name)?.label;
	if (label) return label;
	return name.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const searchTerm = ref(getLabel(props.modelValue || ""));
const internalModelValue = ref(props.modelValue);
const isOpen = ref(false);
const iconNames = ref<string[]>([]);
const headerSearch = ref<{ $el?: HTMLElement } | null>(null);

const selectedOption = computed(() =>
	internalModelValue.value ? optionsByValue.value.get(internalModelValue.value) : undefined,
);

watch(
	() => props.modelValue,
	(newValue) => {
		internalModelValue.value = newValue;
		if (!isOpen.value) {
			searchTerm.value = newValue ? getLabel(newValue) : "";
		}
	},
);

watch(isOpen, async (open) => {
	if (!hasTrigger.value) return;
	searchTerm.value = open
		? ""
		: internalModelValue.value
			? getLabel(internalModelValue.value)
			: "";
	if (!open) return;
	await nextTick();
	headerSearch.value?.$el?.focus?.();
});

onMounted(() => {
	const spriteContainer = document.getElementById("lucide-sprite");
	if (!spriteContainer) {
		console.warn("Lucide sprite not found! Make sure to use the spritePlugin.");
		return;
	}

	const symbols = spriteContainer.getElementsByTagName("symbol");
	const names: string[] = [];
	for (let i = 0; i < symbols.length; i++) {
		const symbol = symbols[i];
		names.push(symbol.id);
	}
	iconNames.value = names;
});

function matchesOption(option: IconPickerOption, term: string) {
	const label = (option.label ?? option.value).replace(/-/g, " ").toLowerCase();
	return label.includes(term) || option.value.toLowerCase().includes(term);
}

const filteredSections = computed(() => {
	const term = searchTerm.value.trim().toLowerCase();
	return props.sections
		.map((section) => ({
			label: section.label,
			options: term
				? section.options.filter((option) => matchesOption(option, term))
				: section.options,
		}))
		.filter((section) => section.options.length > 0);
});

const filteredIcons = computed(() => {
	if (!searchTerm.value) return iconNames.value;
	const lowerSearch = searchTerm.value.toLowerCase();
	return iconNames.value.filter((name) =>
		name.replace(/-/g, " ").toLowerCase().includes(lowerSearch),
	);
});

const hasResults = computed(
	() => filteredIcons.value.length > 0 || filteredSections.value.length > 0,
);

const onUpdateModelValue = (value: string | null) => {
	internalModelValue.value = value;
	emit("update:modelValue", value);
	searchTerm.value = value ? getLabel(value) : "";
	isOpen.value = false;
};

const handleInputChange = (event: Event) => {
	const target = event.target as HTMLInputElement;
	searchTerm.value = target.value;
	isOpen.value = true;

	if (searchTerm.value === "") {
		internalModelValue.value = null;
		emit("update:modelValue", null);
	}
	emit("input", searchTerm.value);
};

const handleHeaderInput = (event: Event) => {
	searchTerm.value = (event.target as HTMLInputElement).value;
	isOpen.value = true;
	emit("input", searchTerm.value);
};

const pickFirst = () => {
	const first = filteredSections.value[0]?.options[0]?.value ?? filteredIcons.value[0];
	if (first) onUpdateModelValue(first);
};

const handleOpenChange = (open: boolean) => {
	isOpen.value = open;
	if (!open && !hasTrigger.value) {
		searchTerm.value = internalModelValue.value ? getLabel(internalModelValue.value) : "";
	}
};

const handleClick = () => {
	if (props.openOnClick) isOpen.value = true;
};

const handleFocus = (event: FocusEvent) => {
	if (props.openOnFocus) isOpen.value = true;
	emit("focus", event);
};

const handleBlur = (event: FocusEvent) => {
	emit("blur", event);
};

const reset = () => {
	searchTerm.value = "";
	internalModelValue.value = null;
	emit("update:modelValue", null);
};

const variantClasses = computed(() => {
	const borderCss =
		"border focus-within:border-outline-gray-4 focus-within:ring-2 focus-within:ring-outline-gray-3";

	return {
		subtle: `${borderCss} bg-surface-gray-2 hover:bg-surface-gray-3 border-transparent`,
		outline: `${borderCss} border-outline-gray-2`,
		ghost: "",
	}[props.variant];
});

defineExpose({
	reset,
});
</script>

<template>
	<div class="relative">
		<ComboboxRoot
			:model-value="internalModelValue"
			@update:modelValue="onUpdateModelValue"
			@update:open="handleOpenChange"
			:ignore-filter="true"
			:open="isOpen"
		>
			<ComboboxAnchor v-if="hasTrigger" as-child @click="isOpen = !isOpen">
				<slot name="trigger" :value="internalModelValue" :open="isOpen" />
			</ComboboxAnchor>

			<ComboboxAnchor
				v-else
				class="flex h-7 w-full items-center justify-between gap-2 rounded px-2 py-1 transition-colors"
				:class="{
					'opacity-50 pointer-events-none': disabled,
					[variantClasses]: true,
				}"
				@click="handleClick"
			>
				<div class="flex items-center gap-2 flex-1 overflow-hidden">
					<IconGlyph
						:name="internalModelValue || 'circle-dashed'"
						:svg="selectedOption?.svg"
						class="w-4 h-4 flex-shrink-0"
					/>
					<ComboboxInput
						:value="searchTerm"
						@input="handleInputChange"
						@focus="handleFocus"
						@blur="handleBlur"
						@keydown.enter.prevent="pickFirst"
						class="bg-transparent p-0 focus:outline-0 border-0 focus:border-0 focus:ring-0 text-base text-ink-gray-8 h-full placeholder:text-ink-gray-4 w-full"
						:placeholder="placeholder || 'Select an icon...'"
						:disabled="disabled"
						autocomplete="off"
					/>
				</div>
				<ComboboxTrigger :disabled="disabled">
					<Icon name="chevron-down" class="h-4 w-4 text-ink-gray-5" />
				</ComboboxTrigger>
			</ComboboxAnchor>

			<ComboboxPortal>
				<ComboboxContent
					class="z-10 w-60 mt-1 bg-surface-elevation-2 overflow-hidden rounded-lg shadow-2xl"
					position="popper"
					@openAutoFocus.prevent
					@closeAutoFocus.prevent
					:align="props.placement || 'start'"
				>
					<div
						v-if="hasTrigger"
						class="flex items-center gap-2 border-b border-outline-gray-1 px-3"
						data-slot="content-search"
					>
						<ComboboxInput
							ref="headerSearch"
							:value="searchTerm"
							@input="handleHeaderInput"
							@keydown.enter.prevent="pickFirst"
							class="min-w-0 flex-1 bg-transparent px-0 py-2 focus:outline-0 border-0 focus:border-0 focus:ring-0 text-base text-ink-gray-8 placeholder:text-ink-gray-4"
							:placeholder="placeholder || 'Search icons'"
							autocomplete="off"
						/>
					</div>
					<ComboboxViewport class="max-h-60 overflow-auto p-2">
						<ComboboxEmpty
							v-if="!hasResults"
							class="text-ink-gray-5 text-base text-center py-1.5 px-2.5"
						>
							<template v-if="searchTerm">
								No icons found for "{{ searchTerm }}"
							</template>
							<template v-else> No icons available. </template>
						</ComboboxEmpty>

						<template v-for="section in filteredSections" :key="section.label">
							<p v-if="section.label" class="px-1 pb-1 text-p-sm text-ink-gray-5">
								{{ section.label }}
							</p>
							<div class="flex flex-wrap">
								<button
									v-for="option in section.options.slice(0, props.maxIcons)"
									:key="option.value"
									@click="onUpdateModelValue(option.value)"
									type="button"
									class="w-8 h-8 flex items-center justify-center rounded hover:bg-surface-gray-3 transition-colors"
									:class="{
										'bg-surface-gray-3': internalModelValue === option.value,
									}"
									:title="option.label ?? getLabel(option.value)"
								>
									<IconGlyph :name="option.value" :svg="option.svg" class="w-4 h-4" />
								</button>
							</div>
						</template>

						<p
							v-if="filteredIcons.length > 0 && filteredSections.length > 0"
							class="px-1 pb-1 pt-2 text-p-sm text-ink-gray-5"
						>
							{{ lucideSectionLabel }}
						</p>
						<div v-if="filteredIcons.length > 0" class="flex flex-wrap">
							<button
								v-for="iconName in filteredIcons.slice(0, props.maxIcons)"
								:key="iconName"
								@click="onUpdateModelValue(iconName)"
								type="button"
								class="w-8 h-8 flex items-center justify-center rounded hover:bg-surface-gray-3 transition-colors"
								:class="{
									'bg-surface-gray-3': internalModelValue === iconName,
								}"
								:title="getLabel(iconName)"
							>
								<Icon :name="iconName" class="w-4 h-4" />
							</button>
						</div>
					</ComboboxViewport>
				</ComboboxContent>
			</ComboboxPortal>
		</ComboboxRoot>
	</div>
</template>
