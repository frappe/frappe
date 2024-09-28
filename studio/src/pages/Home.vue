<template>
	<div class="h-screen flex-col overflow-hidden bg-white">
		<div class="toolbar sticky top-0 z-10 flex h-14 items-center justify-center bg-white p-2 shadow-sm">
			<div class="absolute left-3 flex items-center">
				<router-link class="flex items-center gap-2" :to="{ name: 'Home' }">
					<h1 class="text-md mt-[2px] font-semibold leading-5 text-gray-800">Studio</h1>
				</router-link>
			</div>
		</div>

		<div class="flex h-full flex-col items-center px-20 py-10">
			<div class="flex w-full flex-row justify-between">
				<div class="text-lg font-semibold text-gray-800">All Apps</div>
				<Button variant="solid" icon-left="plus" @click="showDialog = true">New App</Button>
			</div>
			<div class="mt-5 grid w-full grid-cols-5 items-start gap-5">
				<router-link
					class="flex flex-col justify-center gap-1 rounded-lg border-2 p-5"
					v-for="app in studioApps.data"
					:to="{ name: 'StudioApp', params: { appID: app.name } }"
					:key="app.name"
				>
					<div class="font-semibold text-gray-800">{{ app.app_title }}</div>
					<UseTimeAgo v-slot="{ timeAgo }" :time="app.modified">
						<p class="mt-1 block text-xs text-gray-500">Edited {{ timeAgo }}</p>
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
					<Input label="App Title" type="text" variant="outline" v-model="newApp.app_title" />

					<div class="flex w-full flex-col gap-1">
						<label class="block text-xs text-gray-600">App Route</label>
						<div class="relative flex items-stretch">
							<Input
								type="text"
								variant="outline"
								class="w-full [&>div>input]:pl-[100px]"
								:hideClearButton="true"
								v-model="newApp.route"
							/>

							<!-- App Route Prefix -->
							<div
								class="absolute bottom-[1px] left-[1px] flex items-center rounded-l-[0.4rem] bg-gray-100 text-gray-700"
							>
								<span class="flex h-[1.65rem] items-center text-nowrap px-2 py-0 text-base">
									studio-app/
								</span>
							</div>
						</div>
					</div>
				</div>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import { ref } from "vue"
import { useRouter } from "vue-router"
import { studioApps } from "@/data/studioApps"
import { UseTimeAgo } from "@vueuse/components"
import Input from "@/components/Input.vue"

const showDialog = ref(false)
const emptyAppState = {
	app_title: "",
	route: "",
}
const newApp = ref({ ...emptyAppState })
const router = useRouter()

const createStudioApp = (app) => {
	studioApps.insert
		.submit({
			app_title: app.app_title,
			route: `studio-app/${app.route}`,
		})
		.then((res) => {
			showDialog.value = false
			newApp.value = { ...emptyAppState }
			router.push({ name: "StudioApp", params: { appID: res.name } })
		})
}
</script>
