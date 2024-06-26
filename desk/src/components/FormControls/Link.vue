<template>
	<div class="flex flex-col gap-1.5">
		<span v-if="props.label" class="block text-xs text-gray-600">
			{{ props.label }}
		</span>
		<Autocomplete
			ref="autocompleteRef"
			size="sm"
			:modelValue="selectedOptions"
			:placeholder="`Select ${doctype}`"
			:options="options.data"
			:multiple="props.multiple"
			@update:modelValue="(val: AutocompleteValue | AutocompleteValue[]) => updateSelectedOptions(val)"
		/>
	</div>
</template>

<script setup lang="ts">
import { AutocompleteValue, SearchLinkOption } from "@/types/controls"
import { createResource, Autocomplete, debounce } from "frappe-ui"
import { ref, watch } from "vue"

const props = withDefaults(
	defineProps<{
		doctype: string
		label?: string
		filters?: Record<string, any>
		multiple?: boolean
		modelValue: string
	}>(),
	{
		multiple: false,
		label: "",
		filters: () => ({}),
	}
)

const emit = defineEmits(["update:modelValue"])

const autocompleteRef = ref<InstanceType<typeof Autocomplete>>(null)
const searchText = ref("")

const selectedOptions = ref<AutocompleteValue[] | string>(
	props.multiple
		? props.modelValue.length
			? props.modelValue.split(",").map((v) => ({ label: v, value: v }))
			: []
		: props.modelValue
)

const updateSelectedOptions = (val: AutocompleteValue | AutocompleteValue[]) => {
	if (Array.isArray(val)) {
		val = val.filter((v) => v.value != "")
		selectedOptions.value = val
		emit("update:modelValue", val.map((v) => v.value).join(","))
	} else {
		selectedOptions.value = val.value
		emit("update:modelValue", val.value)
	}
}

const options = createResource({
	url: "frappe.desk.search.search_link",
	makeParams() {
		return {
			doctype: props.doctype,
			txt: searchText.value,
			filters: props.filters,
		}
	},
	transform: (data: SearchLinkOption[]) => {
		return data.map((doc) => {
			return {
				label: doc.value,
				value: doc.value,
			}
		})
	},
})

const reloadOptions = debounce(() => {
	options.reload()
}, 300)

watch(
	() => props.doctype,
	() => {
		if (!props.doctype || props.doctype === options.doctype) return
		reloadOptions()
	},
	{ immediate: true }
)

watch(
	() => autocompleteRef.value?.query,
	(val: string) => {
		val = val || ""
		if (searchText.value === val) return
		searchText.value = val
		reloadOptions()
	},
	{ immediate: true }
)
</script>
