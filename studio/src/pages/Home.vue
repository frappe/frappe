<template>
	<div class="h-screen flex-col overflow-hidden bg-white">
		<div
			class="toolbar sticky top-0 z-10 flex h-14 items-center justify-between bg-white px-3 py-2 shadow-sm"
		>
			<Dropdown :options="[{ label: 'Logout', icon: 'log-out', onClick: () => session.logout() }]">
				<template v-slot="{ open }">
					<div class="flex cursor-pointer items-center gap-2">
						<StudioLogo class="h-7 w-7"></StudioLogo>
						<router-link class="flex items-center gap-2" :to="{ name: 'Home' }">
							<h1 class="text-md mt-[2px] font-semibold leading-5 text-gray-800">Studio</h1>
						</router-link>
						<FeatherIcon :name="open ? 'chevron-up' : 'chevron-down'" class="h-4 w-4 text-gray-700" />
					</div>
				</template>
			</Dropdown>

			<Button variant="solid" icon-left="plus" @click="showDialog = true">New App</Button>
		</div>

		<div class="flex h-full flex-col items-center px-20 py-10">
			<div class="flex w-full flex-row justify-between">
				<div class="text-lg font-semibold text-gray-800">All Apps</div>
				<div class="relative flex">
					<Input
						class="w-48"
						type="text"
						variant="outline"
						placeholder="Search"
						v-model="searchFilter"
						autofocus
					>
						<template #prefix>
							<FeatherIcon name="search" class="h-4 w-4 text-gray-500" />
						</template>
					</Input>
				</div>
			</div>
			<div class="mt-5 grid w-full grid-cols-5 items-start gap-5">
				<router-link
					class="flex flex-col justify-center gap-1 rounded-lg border-2 p-5"
					v-for="app in appList"
					:to="{ name: 'StudioApp', params: { appID: app.name } }"
					:key="app.name"
				>
					<div class="font-semibold text-gray-800">{{ app.app_title }}</div>
					<UseTimeAgo v-slot="{ timeAgo }" :time="app.creation">
						<p class="mt-1 block text-xs text-gray-500">Created {{ timeAgo }}</p>
					</UseTimeAgo>
				</router-link>
			</div>
		</div>

		<Dialog
			v-model="showDialog"
			:options="{
				title: 'New App',
				width: 'md',
				actions: [
					{
						label: 'Create',
						variant: 'solid',
						onClick: () => createStudioApp(newApp),
					},
				],
			}"
		>
			<template #body-content>
				<div class="flex flex-col gap-3">
					<FormControl label="App Title" type="text" variant="outline" v-model="newApp.app_title" />
					<FormControl label="App Route" type="text" variant="outline" v-model="newApp.route" />
				</div>
			</template>
		</Dialog>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { Dialog } from "frappe-ui"
import { useRouter } from "vue-router"
import { studioApps } from "@/data/studioApps"
import { UseTimeAgo } from "@vueuse/components"
import Input from "@/components/Input.vue"
import StudioLogo from "@/components/Icons/StudioLogo.vue"
import type { NewStudioApp, StudioApp } from "@/types/Studio/StudioApp"
import session from "@/utils/session"
import { watchDebounced } from "@vueuse/core"

const showDialog = ref(false)
const emptyAppState = {
	app_title: "",
	route: "",
}
const newApp = ref({ ...emptyAppState })
const router = useRouter()

const searchFilter = ref("")
const appList = ref<StudioApp[]>([])

const fetchApps = () => {
	appList.value = studioApps.data
	if (searchFilter.value) {
		appList.value = studioApps.data?.filter((app: StudioApp) =>
			app.app_title.toLowerCase().includes(searchFilter.value?.toLowerCase()),
		)
	}
}

watchDebounced(searchFilter, fetchApps, { debounce: 300, immediate: true })

const createStudioApp = (app: NewStudioApp) => {
	studioApps.insert
		.submit({
			app_title: app.app_title,
			route: app.route,
		})
		.then((res: StudioApp) => {
			showDialog.value = false
			newApp.value = { ...emptyAppState }
			router.push({ name: "StudioApp", params: { appID: res.name } })
		})
}
</script>
