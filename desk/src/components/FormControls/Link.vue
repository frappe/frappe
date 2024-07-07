<template>
	<div class="flex flex-col gap-1.5">
		<span v-if="props.label" class="block text-xs text-gray-600">
			{{ props.label }}
		</span>
		<Autocomplete
			ref="autocompleteRef"
			size="sm"
			v-model="value"
			:placeholder="`Select ${doctype}`"
			:options="options.data"
			:label="label"
		/>
	</div>
</template>

<script setup lang="ts">
import { SelectOption, SearchLinkOption } from "@/types/controls"
import { createResource, Autocomplete, debounce } from "frappe-ui"
import { ref, computed, watch } from "vue"

const props = withDefaults(
	defineProps<{
		doctype: string
		modelValue: string
		label?: string
		filters?: Record<string, any>
	}>(),
	{
		label: "",
		filters: () => ({}),
	}
)

const emit = defineEmits(["update:modelValue"])

const autocompleteRef = ref<InstanceType<typeof Autocomplete>>(null)
const searchText = ref("")

const value = computed({
	get: () => props.modelValue,
	set: (val: SelectOption | string): void => {
		if (typeof val === "string") {
			emit("update:modelValue", val)
		} else {
			emit("update:modelValue", val?.value || "")
		}
	},
})

const options = createResource({
	url: "frappe.desk.search.search_link",
	params: {
		doctype: props.doctype,
		txt: searchText.value,
		filters: props.filters,
	},
	method: "POST",
	transform: (data: SearchLinkOption[]) => {
		return data.map((doc) => {
			return {
				label: doc.value,
				value: doc.value,
			}
		})
	},
})

const reloadOptions = debounce((searchTextVal: string) => {
	options.update({
		params: {
			txt: searchTextVal,
			doctype: props.doctype,
		},
	})
	options.reload()
}, 300)

watch(
	() => props.doctype,
	() => {
		if (!props.doctype || props.doctype === options.doctype) return
		reloadOptions("")
	},
	{ immediate: true }
)

watch(
	() => autocompleteRef.value?.query,
	(val: string) => {
		val = val || ""
		if (searchText.value === val) return
		searchText.value = val
		reloadOptions(val)
	},
	{ immediate: true }
)
</script>
