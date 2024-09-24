<template>
	<div class="flex flex-col gap-5">
		<div class="flex flex-col gap-2">
			<div v-for="(resource, name) in store.resources" :key="name">
				<ObjectBrowser :object="resource" :name="name" />
			</div>
		</div>

		<PageResourceManager v-if="store.activePage" :page="store.activePage" />
	</div>
</template>

<script setup>
import useStudioStore from "@/stores/studioStore"
import PageResourceManager from "@/components/PageResourceManager.vue"
import ObjectBrowser from "@/components/ObjectBrowser.vue"

const store = useStudioStore()
</script>
