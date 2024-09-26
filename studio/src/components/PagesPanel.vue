<template>
	<div class="flex h-full flex-col">
		<div class="flex flex-col space-y-1">
			<div class="w-full" v-for="page in store.appPages" :key="page.name">
				<router-link
					:to="{
						name: 'StudioPage',
						params: { appID: store.activeApp?.name, pageID: page.page_name },
					}"
					class="flex cursor-pointer items-center gap-2 truncate rounded px-2 py-2 transition duration-300 ease-in-out"
					:class="[
						store.activePage?.name === page.page_name
							? 'bg-gray-200 text-gray-900'
							: 'hover:bg-gray-50 hover:text-gray-700',
					]"
				>
					<div class="flex items-center gap-1 truncate text-base text-gray-700">
						{{ page.page_title }}
					</div>
				</router-link>
			</div>
		</div>
	</div>
</template>

<script setup>
import useStudioStore from "@/stores/studioStore"

const store = useStudioStore()
</script>
