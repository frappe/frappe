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

<script setup>
import { createResource, Autocomplete, debounce } from "frappe-ui"
import { ref, computed, watch } from "vue"

const props = defineProps({
	doctype: {
		type: String,
		required: true,
	},
	modelValue: {
		type: String,
		required: true,
		default: "",
	},
	label: {
		type: String,
		required: false,
	},
	filters: {
		type: Object,
		default: {},
	},
})

const emit = defineEmits(["update:modelValue"])

const autocompleteRef = ref(null)
const searchText = ref("")

const value = computed({
	get: () => props.modelValue,
	set: (val) => {
		emit("update:modelValue", val?.value || "")
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
	transform: (data) => {
		return data.map((doc) => {
			return {
				label: doc.value,
				value: doc.value,
			}
		})
	},
})

const reloadOptions = debounce((searchTextVal) => {
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
		if (props.doctype === options.doctype) return
		reloadOptions("")
	},
	{ immediate: true }
)

watch(
	() => autocompleteRef.value?.query,
	(val) => {
		val = val || ""
		if (searchText.value === val) return
		searchText.value = val
		reloadOptions(val)
	},
	{ immediate: true }
)
</script>
