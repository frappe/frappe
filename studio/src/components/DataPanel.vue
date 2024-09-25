<template>
	<div class="flex flex-col p-4">
		<CollapsibleSection sectionName="Resources">
			<div class="flex flex-col gap-2" v-if="!isObjectEmpty(store.resources)">
				<div v-for="(resource, name) in store.resources" :key="name">
					<ObjectBrowser :object="resource" :name="name" />
				</div>
			</div>

			<EmptyState v-else message="No resources added" />

			<div class="flex flex-col" v-if="store.activePage">
				<Button @click="showAddResourceDialog = true">Add Resource</Button>
				<ResourceDialog v-model:showDialog="showAddResourceDialog" @addResource="addResource" />
			</div>
		</CollapsibleSection>
	</div>
</template>

<script setup>
import { ref } from "vue"
import useStudioStore from "@/stores/studioStore"
import CollapsibleSection from "@/components/CollapsibleSection.vue"
import ObjectBrowser from "@/components/ObjectBrowser.vue"
import EmptyState from "@/components/EmptyState.vue"
import ResourceDialog from "@/components/ResourceDialog.vue"

import { isObjectEmpty, getAutocompleteValues } from "@/utils/helpers"
import { studioResources, studioPageResources } from "@/data/studioResources"

/**
 * Insert resource into DB
 * Attach resource to page
 * fetch resources attached to page in store
 * show resources on the data panel
 */

const store = useStudioStore()
const showAddResourceDialog = ref(false)

const attachResource = async (resource) => {
	studioPageResources.insert
		.submit({
			studio_resource: resource.name,
			parent: store.activePage?.name,
			parenttype: "Studio Page",
			parentfield: "resources",
		})
		.then(async () => {
			await store.setPageResources(store.activePage)
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
			studioPageResources.filters = { parent: store.activePage?.name }
			attachResource(res)
		})
}
</script>
