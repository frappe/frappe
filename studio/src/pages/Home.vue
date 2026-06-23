<template>
	<div class="isolate h-screen flex-col overflow-hidden bg-surface-base">
		<div
			class="toolbar sticky top-0 z-10 flex h-14 items-center justify-between border-b border-outline-gray-2 bg-surface-base px-3 py-2"
		>
			<Dropdown :options="[{ label: 'Logout', icon: 'lucide-log-out', onClick: () => session.logout() }]">
				<template v-slot="{ open }">
					<div class="flex cursor-pointer items-center gap-2">
						<StudioLogo class="h-7 w-7"></StudioLogo>
						<router-link class="flex items-center gap-2" :to="{ name: 'Home' }">
							<h1 class="text-md-semibold mt-[2px] leading-5 text-ink-gray-7">Studio</h1>
						</router-link>
						<FeatherIcon :name="open ? 'chevron-up' : 'chevron-down'" class="h-4 w-4 text-ink-gray-6" />
					</div>
				</template>
			</Dropdown>
			<Button variant="solid" icon-left="lucide-plus" @click="showAppDialog = true">New App</Button>
		</div>

		<div class="flex h-full flex-col items-center px-20 py-10">
			<div class="flex w-full flex-row justify-between">
				<div class="text-lg-semibold text-ink-gray-7">All Apps</div>
				<div class="relative flex">
					<Input
						class="w-48"
						type="text"
						variant="outline"
						placeholder="Search"
						v-model="searchFilter"
						autofocus
						@input="
							(value: string) => {
								searchFilter = value
							}
						"
					>
						<template #prefix>
							<FeatherIcon name="search" class="h-4 w-4 text-ink-gray-4" />
						</template>
					</Input>
				</div>
			</div>

			<section class="mt-5 w-full">
				<div v-if="!studioApps.data?.length && !searchFilter" class="col-span-full">
					<p class="mt-4 text-base text-ink-gray-4">
						You don't have any apps yet. Click on the "+ New App" button to create a new app
					</p>
				</div>
				<div v-else-if="!studioApps.data?.length" class="col-span-full">
					<p class="mt-4 text-base text-ink-gray-4">No matching apps found</p>
				</div>
				<div v-else class="grid w-full grid-cols-5 items-start gap-5">
					<router-link
						class="flex flex-col justify-center gap-1 rounded-lg border-2 p-4"
						v-for="app in studioApps.data"
						:to="{ name: 'StudioApp', params: { appID: app.name } }"
						:key="app.name"
					>
						<div class="group flex flex-row justify-between">
							<div class="font-semibold text-ink-gray-7">{{ app.app_title }}</div>
							<div class="invisible shrink-0 group-hover:visible has-[[data-state=open]]:visible">
								<Dropdown
									:options="[
										{
											label: 'Edit',
											onClick: () => {
												activeApp = app
												showAppDialog = true
											},
											icon: 'lucide-edit',
										},
										{ label: 'View in Desk', onClick: () => openInDesk(app), icon: 'lucide-arrow-up-right' },
										{
											label: 'Delete',
											onClick: () => store.deleteApp(app.name, app.app_title),
											icon: 'lucide-trash-2',
											theme: 'red',
										},
									]"
									:button="{
										icon: 'lucide-more-horizontal',
										label: 'App Options',
										variant: 'ghost',
									}"
									size="sm"
									side="right"
								/>
							</div>
						</div>
						<UseTimeAgo v-slot="{ timeAgo }" :time="app.creation">
							<p class="mt-1 block text-xs text-ink-gray-4">Created {{ timeAgo }}</p>
						</UseTimeAgo>
					</router-link>
				</div>
			</section>
		</div>

		<AppDialog v-model:showDialog="showAppDialog" :app="activeApp" @after-leave="() => (activeApp = null)" />
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { studioApps } from "@/data/studioApps"
import { UseTimeAgo } from "@vueuse/components"
import Input from "@/components/Input.vue"
import StudioLogo from "@/components/Icons/StudioLogo.vue"
import session from "@/utils/session"
import { watchDebounced } from "@vueuse/core"
import useStudioStore from "@/stores/studioStore"
import { openInDesk } from "@/utils/helpers"

const store = useStudioStore()

const searchFilter = ref("")

const fetchApps = () => {
	const filters = {} as any
	if (searchFilter.value) {
		filters["app_title"] = ["like", `%${searchFilter.value}%`]
	}
	studioApps.update({
		filters,
	})
	studioApps.fetch()
}

watchDebounced(searchFilter, fetchApps, { debounce: 300, immediate: true })

const showAppDialog = ref(false)
const activeApp = ref()
</script>
