<template>
	<div class="flex flex-col gap-5">
		<div class="flex flex-col gap-2">
			<div v-for="(resource, name) in store.resources" :key="name">
				<span class="text-xs text-gray-700"> {{ name }}</span>
				<pre>{{ resource }}</pre>
			</div>
		</div>

		<PageResourceManager v-if="store.activePage" :page="store.activePage" />
	</div>
</template>

<script setup>
import useStore from "@/store"
import PageResourceManager from "@/components/PageResourceManager.vue"

const store = useStore()
</script>
