<template>
	<div class="flex flex-col p-4">
		<CollapsibleSection sectionName="Resources">
			<div class="flex flex-col gap-2" v-if="!isObjectEmpty(store.resources)">
				<div v-for="(resource, name) in store.resources" :key="name">
					<ObjectBrowser :object="resource" :name="name" />
				</div>
			</div>

			<EmptyState v-else message="No resources added" />
			<PageResourceManager v-if="store.activePage" :page="store.activePage" />
		</CollapsibleSection>
	</div>
</template>

<script setup>
import useStudioStore from "@/stores/studioStore"
import CollapsibleSection from "@/components/CollapsibleSection.vue"
import PageResourceManager from "@/components/PageResourceManager.vue"
import ObjectBrowser from "@/components/ObjectBrowser.vue"
import EmptyState from "@/components/EmptyState.vue"
import { isObjectEmpty } from "@/utils/helpers"

const store = useStudioStore()
</script>
