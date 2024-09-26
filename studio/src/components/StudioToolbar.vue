<template>
	<div class="toolbar flex h-14 items-center justify-center bg-white p-2 shadow-sm">
		<div class="absolute left-3 flex items-center">
			<router-link class="flex items-center gap-2" :to="{ name: 'Home' }">
				<h1 class="text-md mt-[2px] font-semibold leading-5 text-gray-800">Studio</h1>
			</router-link>
		</div>

		<div>
			<Popover transition="default" placement="bottom" popoverClass="!absolute top-0 !mt-[20px]">
				<template #target="{ togglePopover, isOpen }">
					<div class="flex cursor-pointer items-center gap-2 p-2">
						<div class="flex h-6 items-center text-base text-gray-800" v-if="!store.activePage">
							Loading...
						</div>
						<div @click="togglePopover" v-else class="flex items-center gap-1">
							<span class="max-w-48 truncate text-base text-gray-800">
								{{ store?.activePage?.page_title || "My Page" }}
							</span>
							-
							<span class="flex max-w-96 truncate text-base text-gray-600">
								{{ routeString }}
							</span>
						</div>
						<FeatherIcon
							name="external-link"
							v-if="store.activePage && store.activePage.published"
							class="h-[14px] w-[14px] !text-gray-700 dark:!text-gray-200"
							@click="store.openPageInBrowser(store.activePage)"
						>
						</FeatherIcon>
					</div>
				</template>
				<template #body="{ isOpen }">
					<div class="flex w-96 flex-col gap-3 rounded bg-white p-4 shadow-lg" v-if="store.activePage">
						<PageOptions
							v-if="store.activePage"
							:page="store.activePage"
							:app="store.activeApp"
							:isOpen="isOpen"
						></PageOptions>
					</div>
				</template>
			</Popover>
		</div>

		<div class="absolute right-3 flex items-center">
			<Button
				size="sm"
				variant="solid"
				@click="
					() => {
						publishing = true
						store.publishPage().finally(() => (publishing = false))
					}
				"
			>
				Publish
			</Button>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import useStudioStore from "@/stores/studioStore"

import PageOptions from "@/components/PageOptions.vue"

const store = useStudioStore()
const publishing = ref(false)

const routeString = computed(() => store.activePage?.route || "/")
</script>
