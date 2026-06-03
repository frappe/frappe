<template>
	<div data-slot="link" class="contents">
		<Combobox
			ref="comboboxRef"
			v-bind="$attrs"
			v-model="model"
			v-model:open="open"
			class="group !gap-1"
			:label="label"
			:description="description"
			:error="error"
			:required="required"
			:id="id"
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
			<template v-else-if="showClear" #suffix>
				<button
					type="button"
					aria-label="Clear"
					data-slot="clear"
					class="group-hover:grid group-focus:grid group-focus-within:grid hidden size-4 place-items-center rounded-sm text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-7 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
					@click="clearValue"
					@pointerdown.stop
				>
					<span class="lucide-x size-3.5" />
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
	</div>
</template>

<script setup lang="ts">
import { computed, ref, useSlots, watch } from "vue";
import { Combobox, createResource, frappeRequest, debounce } from "frappe-ui";
import type { ComboboxOption, ComboboxCustomOption } from "frappe-ui";
import type { LinkExposed, LinkOption, LinkProps, LinkEmits } from "./types";

const props = withDefaults(defineProps<LinkProps>(), {
	filters: () => ({}),
	creatable: false,
	disabled: false,
});

const model = defineModel<string | null>({ default: null });
const open = defineModel<boolean>("open", { default: false });
const comboboxRef = ref<{ focus: () => void } | null>(null);

const emit = defineEmits<LinkEmits>();

defineOptions({ inheritAttrs: false });

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

const showClear = computed(() => !props.disabled && !!model.value && !props.required);

const loadOptions = (txt: string = "") => {
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
