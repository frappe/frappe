<template>
	<Combobox
		ref="comboboxRef"
		v-model="model"
		v-model:open="open"
		class="group !gap-1 [&_[data-slot=input]:disabled]:text-ink-gray-4"
		:class="{ 'w-full': panel }"
		:variant="panel ? 'ghost' : undefined"
		:size="panel ? 'sm' : undefined"
		:label="panel ? undefined : label"
		:description="panel ? undefined : description"
		:error="panel ? undefined : error"
		:required="required"
		:options="linkOptions"
		:filterable="!idLabels"
		:disabled="disabled"
		:placeholder="shownPlaceholder"
		:loading="options.loading.value && !options.data.value"
		@input="onInput(($event.target as HTMLInputElement).value)"
		@focus="onFocus"
	>
		<template v-for="(_, name) in forwardedSlots" #[name]="slotProps" :key="name">
			<slot :name="name" v-bind="slotProps" />
		</template>

		<template v-if="panel" #footer><PickerListFit /></template>

		<template v-if="slots.suffix" #suffix="suffixProps">
			<slot name="suffix" v-bind="suffixProps" />
		</template>
		<template v-else-if="showRedirect || showEdit || showClear" #suffix>
			<button
				v-if="showClear"
				type="button"
				aria-label="Clear"
				data-slot="clear"
				class="group-hover:grid group-focus:grid group-focus-within:grid hidden size-4 place-items-center rounded-1 text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-7 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
				@click.stop="clearValue"
				@pointerdown.stop
			>
				<span class="lucide-x size-3.5" />
			</button>
			<button
				v-if="showEdit"
				type="button"
				aria-label="Edit linked record"
				data-slot="edit"
				class="group-hover:grid group-focus:grid group-focus-within:grid hidden size-4 place-items-center rounded-1 text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-7 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
				@click.stop="emit('edit', model!)"
				@pointerdown.stop
			>
				<span class="lucide-square-pen size-3.5" />
			</button>
			<RecordAnchor
				v-if="showRedirect && href"
				:href="href"
				:aria-label="openLabel"
				:title="openLabel"
				data-slot="redirect"
				class="group-hover:grid group-focus:grid group-focus-within:grid hidden size-4 place-items-center rounded-1 text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-7 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
				@open="emit('redirect', model!)"
				@pointerdown.stop
			>
				<span class="lucide-arrow-up-right size-3.5" />
			</RecordAnchor>
			<button
				v-else-if="showRedirect"
				type="button"
				:aria-label="openLabel"
				:title="openLabel"
				data-slot="redirect"
				class="group-hover:grid group-focus:grid group-focus-within:grid hidden size-4 place-items-center rounded-1 text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-7 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
				@click.stop="emit('redirect', model!)"
				@pointerdown.stop
			>
				<span class="lucide-arrow-up-right size-3.5" />
			</button>
		</template>

		<template v-if="slots['item-create']" #item-create="slotProps">
			<slot name="item-create" v-bind="slotProps" />
		</template>
		<template v-else #item-create="{ query }">
			<div class="flex">
				<span class="truncate">
					Create
					<span v-if="query" class="font-medium text-ink-gray-8">
						{{ query }}
					</span>
				</span>
			</div>
		</template>
	</Combobox>
</template>

<script setup lang="ts">
import { toIdOption } from "./linkOption";
import { computed, onBeforeUnmount, ref, useSlots, watch } from "vue";
import { Combobox, debounce } from "frappe-ui";
import type { ComboboxOption, ComboboxCustomOption } from "frappe-ui";
import { useLinkSearch } from "../../composables/useLinkSearch";
import { translate as __ } from "../../utils/translate";
import RecordAnchor from "./RecordAnchor.vue";
import PickerListFit from "../Fields/PickerListFit.vue";
import { useFittedPlaceholder } from "./fittedPlaceholder";
import type { LinkExposed, LinkProps, LinkEmits } from "./types";

const props = withDefaults(defineProps<LinkProps>(), {
	filters: () => ({}),
	creatable: false,
	href: null,
	redirectable: false,
	editable: false,
	disabled: false,
});

const model = defineModel<string | null>({ default: null });
const open = defineModel<boolean>("open", { default: false });
const comboboxRef = ref<{ focus: () => void } | null>(null);
const placeholderText = computed(
	() => props.placeholder ?? `Search ${props.doctype.toLowerCase()}`
);
const fitted = useFittedPlaceholder(() => placeholderText.value);
const shownPlaceholder = computed(() =>
	props.panel ? fitted.placeholder.value : placeholderText.value
);

const emit = defineEmits<LinkEmits>();

// A panel row hides the mark while the user types, so the text starts at the box's padding.
const typing = ref(false);

const slots = useSlots();

const forwardedSlots = computed(() =>
	Object.fromEntries(
		Object.entries(slots).filter(
			([name]) =>
				name !== "suffix" &&
				name !== "item-create" &&
				!(name === "footer" && props.panel) &&
				!(name === "prefix" && typing.value)
		)
	)
);

const options = useLinkSearch(
	() => props.doctype,
	() => props.filters
);

// The search labels by title; relabelling its options by ID matches `toIdOption` on the raw rows.
const searchOptions = computed(() =>
	props.idLabels ? options.data.value?.map(toIdOption) ?? null : options.data.value
);

const createNewOption: ComboboxCustomOption = {
	type: "custom",
	key: "create",
	label: "Create New",
	slot: "create",
	// Declared, so the row stays last whatever is typed: without it the label is filtered.
	condition: () => true,
	onClick: ({ query }: { query: string }) => emit("create", query),
};

const linkOptions = computed<ComboboxOption[]>(() => {
	let _options: ComboboxOption[] = searchOptions.value || [];
	const known = model.value && _options.some((option: any) => option.value === model.value);
	if (props.title && model.value && !known) {
		_options = [{ label: props.title, value: model.value }, ..._options];
	}
	if (props.creatable) {
		return [..._options, createNewOption];
	}
	return _options;
});

const showClear = computed(() => !props.disabled && !!model.value);
const showRedirect = computed(() => (!!props.href || props.redirectable) && !!model.value);
const openLabel = computed(() => {
	const option: any = linkOptions.value.find((option: any) => option.value === model.value);
	return __("Open {0}", [option?.label ?? model.value]);
});
const showEdit = computed(() => props.editable && !!model.value);

// The server lets the browser keep a search answer this long; an open after it asks again.
const OPTIONS_MAX_AGE_MS = 60_000;
let searched: string | null = null;
let searchedAt = 0;

const loadOptions = (txt: string = "", fresh = false) => {
	searched = txt;
	searchedAt = Date.now();
	void options.search(txt, { fresh });
};

function onFocus(event: FocusEvent) {
	if (props.panel) fitted.fit(event.target as HTMLInputElement);
	showAllOptions();
}

const showAllOptions = () => {
	const expired = Date.now() - searchedAt > OPTIONS_MAX_AGE_MS;
	if (searched !== "" || expired || options.error.value) loadOptions("");
};

// The input's native event, not `update:query`: the Combobox also sets the query to the shown value.
const handleInputChange = debounce((value: string) => {
	loadOptions(value || "");
}, 300);

function onInput(value: string) {
	typing.value = !!props.panel;
	handleInputChange(value);
}

const clearValue = () => {
	model.value = null;
	open.value = false;
	comboboxRef.value?.focus();
};

watch(
	open,
	(isOpen) => {
		if (isOpen) showAllOptions();
		else typing.value = false;
	},
	{ immediate: true }
);
watch(model, () => (typing.value = false));

watch(
	[() => props.doctype, () => props.filters],
	() => {
		searched = null;
		if (open.value) loadOptions("");
	},
	{ deep: true }
);

onBeforeUnmount(() => handleInputChange.cancel());

defineExpose<LinkExposed>({
	reload: () => loadOptions(""),
	search: (text, { fresh = false } = {}) => loadOptions(text, fresh),
	focus: () => comboboxRef.value?.focus(),
});
</script>
