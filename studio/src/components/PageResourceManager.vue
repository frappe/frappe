<template>
	<div class="flex flex-col gap-5">
		<Button @click="showAddResourceDialog = true">Add Resource</Button>
		<ResourceDialog v-model:showDialog="showAddResourceDialog" @addResource="addResource" />
	</div>
</template>

<script setup lang="ts">
import { ref, PropType } from "vue"
import useStore from "@/store"
import ResourceDialog from "@/components/ResourceDialog.vue"

import { StudioPage } from "@/types"
import { getAutocompleteValues } from "@/utils/helpers"

import { studioResources, studioPageResources } from "@/data/studioResources"

const props = defineProps({
	page: {
		type: Object as PropType<StudioPage>,
		required: true,
	},
})

/**
 * Insert resource into DB
 * Attach resource to page
 * fetch resources attached to page in store
 * show resources on the data panel
 */

const store = useStore()
const showAddResourceDialog = ref(false)

const attachResource = async (resource) => {
	studioPageResources.insert
		.submit({
			studio_resource: resource.name,
			parent: props.page?.name,
			parenttype: "Studio Page",
			parentfield: "resources",
		})
		.then(async () => {
			await store.setPageResources(props.page)
			showAddResourceDialog.value = false
		})
}

const addResource = (resource) => {
	if (resource.source === "Existing Resource") {
		attachResource(resource)
		return
	}
	const fields = getAutocompleteValues(resource.fields)

	studioResources.insert
		.submit({
			name: resource.name,
			resource_type: resource.resource_type,
			document_type: resource.document_type,
			document_name: resource.document_name,
			url: resource.url,
			method: resource.method,
			fields: fields,
		})
		.then((res) => {
			studioPageResources.filters = { parent: props.page?.name }
			attachResource(res)
		})
}
</script>
