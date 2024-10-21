<template>
	<div class="flex flex-col p-4">
		<CollapsibleSection sectionName="Data Sources">
			<div class="flex flex-col gap-2" v-if="!isObjectEmpty(store.resources)">
				<div
					v-for="(resource, name) in store.resources"
					:key="name"
					class="group/resource flex flex-row justify-between"
				>
					<ObjectBrowser :object="resource" :name="name" />
					<FeatherIcon
						name="trash"
						class="invisible h-3 w-3 cursor-pointer group-hover/resource:visible"
						@click="deleteResource(resource.docname, name)"
					/>
				</div>
			</div>

			<EmptyState v-else message="No resources added" />

			<div class="mt-2 flex flex-col" v-if="store.activePage">
				<Button icon-left="plus" @click="showAddResourceDialog = true">Add Data Source</Button>
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

import { isObjectEmpty, getAutocompleteValues, confirm } from "@/utils/helpers"
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
	if (resource.source === "Existing Data Source") {
		attachResource(resource)
		return
	}

	studioResources.insert
		.submit({
			name: resource.name,
			resource_type: resource.resource_type,
			document_type: resource.document_type,
			document_name: resource.document_name,
			url: resource.url,
			method: resource.method,
			fields: getAutocompleteValues(resource.fields),
			filters: resource.filters,
			whitelisted_methods: getAutocompleteValues(resource.whitelisted_methods),
			transform_results: resource.transform_results,
			transform: resource.transform,
		})
		.then((res) => {
			studioPageResources.filters = { parent: store.activePage?.name }
			attachResource(res)
		})
}

const deleteResource = async (docname, resource_name) => {
	const confirmed = await confirm(`Are you sure you want to delete the resource ${resource_name}?`)
	if (confirmed) {
		studioPageResources.delete.submit(docname).then(() => {
			store.setPageResources(store.activePage)
		})
	}
}
</script>
