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
						store.activePage?.name === page.page_name ? 'border-[1px] border-gray-300' : 'hover:bg-gray-50',
					]"
				>
					<div
						class="flex items-center gap-1 truncate text-base"
						:class="[
							store.activePage?.name === page.page_name ? 'font-medium text-gray-700' : 'text-gray-500',
						]"
					>
						{{ page.page_title }}
					</div>
					<Badge
						v-if="store.activeApp?.app_home === page.page_name"
						variant="outline"
						size="sm"
						class="text-xs"
						theme="blue"
					>
						App Home
					</Badge>
				</router-link>
			</div>
		</div>

		<router-link
			v-if="store.activeApp"
			:to="{ name: 'StudioPage', params: { appID: store.activeApp?.name, pageID: 'new' } }"
		>
			<Button icon-left="plus" class="mt-5 w-full">New Page</Button>
		</router-link>
	</div>
</template>

<script setup>
import useStudioStore from "@/stores/studioStore"

const store = useStudioStore()
</script>
