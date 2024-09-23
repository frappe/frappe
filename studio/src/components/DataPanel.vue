<template>
	<div class="flex flex-col gap-5">
		<div class="flex flex-col gap-2">
			<div v-for="resource in store.resources" :key="resource.resourceName">
				<span class="text-xs text-gray-700"> {{ resource.resourceName }}</span>
				<pre>{{ resource }}</pre>
			</div>
		</div>

		<Button @click="showAddResourceDialog = true">Add Resource</Button>
		<ResourceDialog v-model:showDialog="showAddResourceDialog" />
	</div>
</template>

<script setup>
import { ref } from "vue"
import useStore from "@/store"
import ResourceDialog from "@/components/ResourceDialog.vue"

const store = useStore()
const showAddResourceDialog = ref(false)
</script>
