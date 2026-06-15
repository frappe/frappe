<template>
	<Combobox
		ref="comboboxRef"
		v-model="model"
		v-model:open="open"
		class="group !gap-1"
		:label="label"
		:description="description"
		:error="error"
		:required="required"
		:options="linkOptions"
		:disabled="disabled"
		:placeholder="placeholder ?? `Search ${doctype.toLowerCase()}`"
		:loading="options.loading && !options.data"
		@update:query="handleInputChange"
		@focus="() => loadOptions('')"
	>
		<template v-for="(_, name) in forwardedSlots" #[name]="slotProps" :key="name">
			<slot :name="name" v-bind="slotProps" />
		</template>

		<template v-if="slots.suffix" #suffix="suffixProps">
			<slot name="suffix" v-bind="suffixProps" />
		</template>
		<template v-else-if="showRedirect || showEdit || showClear" #suffix>
			<button
				v-if="showClear"
				type="button"
				aria-label="Clear"
				data-slot="clear"
				class="group-hover:grid group-focus:grid group-focus-within:grid hidden size-4 place-items-center rounded-sm text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-7 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
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
				class="group-hover:grid group-focus:grid group-focus-within:grid hidden size-4 place-items-center rounded-sm text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-7 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
				@click.stop="emit('edit', model!)"
				@pointerdown.stop
			>
				<span class="lucide-square-pen size-3.5" />
			</button>
			<button
				v-if="showRedirect"
				type="button"
				aria-label="Open linked record"
				data-slot="redirect"
				class="group-hover:grid group-focus:grid group-focus-within:grid hidden size-4 place-items-center rounded-sm text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-7 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
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
import { computed, ref, useSlots, watch } from "vue";
import { Combobox, createResource, frappeRequest, debounce } from "frappe-ui";
import type { ComboboxOption, ComboboxCustomOption } from "frappe-ui";
import type { LinkExposed, LinkOption, LinkProps, LinkEmits } from "./types";

const props = withDefaults(defineProps<LinkProps>(), {
	filters: () => ({}),
	creatable: false,
	redirectable: false,
	editable: false,
	disabled: false,
});

const model = defineModel<string | null>({ default: null });
const open = defineModel<boolean>("open", { default: false });
const comboboxRef = ref<{ focus: () => void } | null>(null);

const emit = defineEmits<LinkEmits>();

const slots = useSlots();

const forwardedSlots = computed(() =>
	Object.fromEntries(
		Object.entries(slots).filter(([name]) => name !== "suffix" && name !== "item-create")
	)
);

const options = createResource({
	url: "frappe.desk.search.search_link",
	params: {
		doctype: props.doctype,
		txt: "",
		filters: props.filters,
	},
	method: "POST",
	resourceFetcher: frappeRequest,
	transform: (data: LinkOption[]): LinkOption[] =>
		data.map((doc: any) => ({
			label: doc.label || doc.value,
			value: doc.value,
			description: doc.description,
		})),
});

const createNewOption: ComboboxCustomOption = {
	type: "custom",
	key: "create",
	label: "Create New",
	slot: "create",
	condition: ({ query }: { query: string }) => Boolean(query.trim()),
	onClick: ({ query }: { query: string }) => emit("create", query),
};

const linkOptions = computed<ComboboxOption[]>(() => {
	const _options = options.data || [];
	if (props.creatable) {
		return [..._options, createNewOption];
	}
	return _options;
});

const showClear = computed(() => !props.disabled && !!model.value);
const showRedirect = computed(() => props.redirectable && !!model.value);
const showEdit = computed(() => props.editable && !!model.value);

const loadOptions = (txt: string = "") => {
	if (!props.doctype) return;
	options.update({
		params: {
			txt,
			doctype: props.doctype,
			filters: props.filters,
		},
	});
	options.reload();
};

const handleInputChange = debounce((value: string) => {
	loadOptions(value || "");
}, 300);

const clearValue = () => {
	model.value = null;
	open.value = false;
	comboboxRef.value?.focus();
};

watch([() => props.doctype, () => props.filters], () => loadOptions(""), {
	immediate: true,
	deep: true,
});

defineExpose<LinkExposed>({ reload: () => loadOptions("") });
</script>
