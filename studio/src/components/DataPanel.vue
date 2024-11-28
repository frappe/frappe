<template>
	<div class="flex flex-col p-4">
		<CollapsibleSection sectionName="Data Sources">
			<div class="flex flex-col gap-2" v-if="!isObjectEmpty(store.resources)">
				<div
					v-for="(resource, name) in store.resources"
					:key="name"
					class="group/resource flex flex-row justify-between"
				>
					<ObjectBrowser :object="resource" :name="name" class="overflow-hidden" />
					<div
						class="invisible -mt-1 ml-auto self-start text-gray-600 group-hover/resource:visible has-[.active-item]:visible"
					>
						<Dropdown :options="getResourceMenu(resource, name)" trigger="click">
							<template v-slot="{ open }">
								<button
									class="flex cursor-pointer items-center rounded-sm p-1 text-gray-700 hover:bg-gray-300"
									:class="open ? 'active-item' : ''"
								>
									<FeatherIcon name="more-horizontal" class="h-3 w-3" />
								</button>
							</template>
						</Dropdown>
					</div>
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

<script setup lang="ts">
import { ref } from "vue"
import useStudioStore from "@/stores/studioStore"
import CollapsibleSection from "@/components/CollapsibleSection.vue"
import ObjectBrowser from "@/components/ObjectBrowser.vue"
import EmptyState from "@/components/EmptyState.vue"
import ResourceDialog from "@/components/ResourceDialog.vue"

import { isObjectEmpty, getAutocompleteValues, confirm, copyToClipboard } from "@/utils/helpers"
import { studioResources, studioPageResources } from "@/data/studioResources"
import { NewResource, Resource } from "@/types/Studio/StudioResource"
import { toast } from "vue-sonner"

/**
 * Insert resource into DB
 * Attach resource to page
 * fetch resources attached to page in store
 * show resources on the data panel
 */

const store = useStudioStore()
const showAddResourceDialog = ref(false)

const attachResource = async (resource: Resource) => {
	studioPageResources.insert
		.submit({
			studio_resource: resource.name,
			parent: store.activePage?.name,
			parenttype: "Studio Page",
			parentfield: "resources",
		})
		.then(async () => {
			if (store.activePage) {
				await store.setPageResources(store.activePage)
			}
			showAddResourceDialog.value = false
		})
}

const addResource = (resource: NewResource) => {
	if (resource.source === "Existing Data Source") {
		attachResource(resource as unknown as Resource)
		return
	}

	studioResources.insert
		.submit({
			name: resource.resource_name,
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
		.then((res: Resource) => {
			studioPageResources.filters = { parent: store.activePage?.name }
			attachResource(res)
		})
}

const deleteResource = async (docname: string, resource_name: string) => {
	const confirmed = await confirm(`Are you sure you want to delete the data source ${resource_name}?`)
	if (confirmed) {
		studioPageResources.delete
			.submit(docname)
			.then(() => {
				if (store.activePage) {
					store.setPageResources(store.activePage)
				}
				toast.success(`Data Source <b>${resource_name}</b> deleted successfully`)
			})
			.catch(() => {
				toast.error(`Failed to delete data source ${resource_name}`)
			})
	}
}

const getResourceMenu = (resource: Resource, name: string) => {
	return [
		{
			label: "Edit",
			icon: "edit",
			onClick: () => {},
		},
		{
			label: "Delete",
			icon: "trash",
			onClick: () => deleteResource(resource.docname, name),
		},
		{
			label: "Copy Object",
			icon: "copy",
			onClick: () => {
				copyToClipboard(resource)
			},
		},
	]
}
</script>
