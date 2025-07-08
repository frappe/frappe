<template>
	<div class="flex h-full flex-col">
		<div class="flex flex-col space-y-1">
			<div class="w-full" v-for="page in store.appPages" :key="page.name">
				<div
					@click="openPage(page)"
					class="group flex cursor-pointer items-center gap-2 truncate rounded px-2 py-2 transition duration-300 ease-in-out"
					:class="[isPageActive(page) ? 'border-[1px] border-gray-300' : 'hover:bg-gray-50']"
				>
					<div
						class="flex items-center gap-1 truncate text-base"
						:class="[isPageActive(page) ? 'font-medium text-gray-700' : 'text-gray-500']"
					>
						{{ page.page_title }} -
						<span class="text-xs">{{ getPageRoute(page) }}</span>
					</div>
					<Badge v-if="isAppHome(page)" variant="outline" size="sm" class="text-xs" theme="blue">
						App Home
					</Badge>

					<!-- Menu -->
					<div
						class="invisible ml-auto flex items-center gap-1.5 text-gray-600 group-hover:visible has-[.active-item]:visible"
					>
						<Dropdown :options="getPageMenu(page)" trigger="click">
							<template v-slot="{ open }">
								<button
									class="flex cursor-pointer items-center rounded-sm p-0.5 text-gray-700 hover:bg-gray-300"
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

		<router-link
			v-if="store.activeApp"
			:to="{ name: 'StudioPage', params: { appID: store.activeApp?.name, pageID: 'new' } }"
		>
			<Button icon-left="plus" class="mt-5 w-full">New Page</Button>
		</router-link>
	</div>
</template>

<script setup lang="ts">
import useStudioStore from "@/stores/studioStore"
import type { StudioPage } from "@/types/Studio/StudioPage"
import { isObjectEmpty } from "@/utils/helpers"
import { useRouter } from "vue-router"

const store = useStudioStore()
const router = useRouter()

const isPageActive = (page: StudioPage) => store.activePage?.name === page.name
const isAppHome = (page: StudioPage) => store.activeApp?.app_home === page.name

const getPageRoute = (page: StudioPage) => {
	if (!store.activeApp) return ""
	return page.route.replace(store.activeApp.route, "")
}

const getPageMenu = (page: StudioPage) => {
	if (isObjectEmpty(store.activeApp)) return []

	const app = store.activeApp!

	return [
		{
			label: "Set as App Home",
			icon: "home",
			condition: () => !isAppHome(page),
			onClick: () => {
				store.updateActiveApp("app_home", page.name)
			},
		},
		{
			label: "Duplicate",
			icon: "copy",
			onClick: () => store.duplicateAppPage(app.name, page),
		},
		{
			label: "Delete",
			icon: "trash",
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
