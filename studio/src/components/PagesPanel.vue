<template>
	<div class="flex h-full flex-col overflow-hidden">
		<div class="flex flex-col space-y-1 overflow-y-auto hide-scrollbar">
			<div class="w-full" v-for="page in store.appPages" :key="page.name">
				<div
					@click="openPage(page)"
					class="group flex cursor-pointer items-center gap-2 truncate rounded px-2 py-2 transition duration-300 ease-in-out"
					:class="[isPageActive(page) ? 'border-[1px] border-outline-gray-2' : 'hover:bg-surface-gray-1']"
				>
					<Tooltip :text="page.published ? 'Published' : 'Draft'" placement="top">
						<div
							class="h-2 w-2 flex-shrink-0 rounded-full"
							:class="page.published ? 'bg-surface-green-6' : 'bg-surface-gray-5'"
						></div>
					</Tooltip>
					<div
						class="flex items-center gap-1 truncate text-base"
						:class="[isPageActive(page) ? 'font-medium text-ink-gray-6' : 'text-ink-gray-4']"
					>
						{{ page.page_title }} -
						<span class="text-xs">{{ page.route }}</span>
					</div>
					<Tooltip text="App Home" placement="top">
						<Badge v-if="isAppHome(page)" variant="subtle" size="sm" class="text-xs">Home</Badge>
					</Tooltip>

					<!-- Menu -->
					<div
						class="invisible ml-auto flex items-center gap-1.5 text-ink-gray-5 group-hover:visible has-[.active-item]:visible"
					>
						<Dropdown :options="getPageMenu(page)" trigger="click">
							<template v-slot="{ open }">
								<button
									class="flex cursor-pointer items-center rounded-sm p-0.5 text-ink-gray-6 hover:bg-surface-gray-4"
									:class="open ? 'active-item' : ''"
								>
									<FeatherIcon name="more-horizontal" class="h-4 w-4" />
								</button>
							</template>
						</Dropdown>
					</div>
				</div>
			</div>
		</div>

		<div class="mt-4 flex-shrink-0">
			<router-link
				v-if="store.activeApp"
				:to="{ name: 'StudioPage', params: { appID: store.activeApp?.name, pageID: 'new' } }"
			>
				<Button icon-left="plus" class="w-full">New Page</Button>
			</router-link>
		</div>
	</div>
</template>

<script setup lang="ts">
import useStudioStore from "@/stores/studioStore"
import type { StudioPage } from "@/types/Studio/StudioPage"
import { isObjectEmpty } from "@/utils/helpers"
import { useRouter } from "vue-router"
import { Dropdown, Button, Badge, Tooltip } from "frappe-ui"

const store = useStudioStore()
const router = useRouter()

const isPageActive = (page: StudioPage) => store.activePage?.name === page.name
const isAppHome = (page: StudioPage) => store.activeApp?.app_home === page.name

const getPageMenu = (page: StudioPage) => {
	if (isObjectEmpty(store.activeApp)) return []

	const app = store.activeApp!

	return [
		{
			label: "Set as App Home",
			icon: "lucide-home",
			condition: () => !isAppHome(page),
			onClick: () => {
				store.updateActiveApp("app_home", page.name)
			},
		},
		{
			label: "Duplicate",
			icon: "lucide-copy",
			onClick: () => store.duplicateAppPage(app.name, page),
		},
		{
			label: "Delete",
			icon: "lucide-trash",
			theme: "red",
			condition: () => !isAppHome(page),
			onClick: async () => {
				await store.deleteAppPage(app.name, page)
				if (isPageActive(page)) {
					router.push({
						name: "StudioPage",
						params: { appID: app.name, pageID: app.app_home },
						replace: true,
					})
				}
			},
		},
	]
}

const openPage = (page: StudioPage) => {
	router.push({
		name: "StudioPage",
		params: { appID: store.activeApp?.name, pageID: page.name },
	})
}
</script>
