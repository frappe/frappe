<template>
	<div class="toolbar flex h-14 items-center justify-center bg-white p-2 shadow-sm">
		<div class="absolute left-3 flex items-center justify-center gap-5">
			<Dropdown
				:options="[
					{ label: 'Back to Dashboard', icon: 'arrow-left', onClick: () => $router.push({ name: 'Home' }) },
					{ label: 'Logout', icon: 'log-out', onClick: () => session.logout() },
				]"
			>
				<template v-slot="{ open }">
					<div class="flex cursor-pointer items-center gap-1">
						<StudioLogo class="h-7 w-7"></StudioLogo>
						<FeatherIcon :name="open ? 'chevron-up' : 'chevron-down'" class="h-4 w-4 text-gray-700" />
					</div>
				</template>
			</Dropdown>

			<div class="flex gap-2">
				<Tooltip
					:text="mode.description"
					:hoverDelay="0.6"
					v-for="mode in [
						{ mode: 'select', icon: 'mouse-pointer', description: 'Select (v)' },
						{ mode: 'container', icon: 'square', description: 'Container (c)' },
					]"
				>
					<Button
						variant="ghost"
						:icon="mode.icon"
						class="text-ink-gray-7 hover:bg-surface-gray-2 focus:!bg-surface-gray-3 [&[active='true']]:bg-surface-gray-3 [&[active='true']]:text-ink-gray-9"
						@click="() => (store.mode = mode.mode as StudioMode)"
						:active="store.mode === mode.mode"
					/>
				</Tooltip>
			</div>
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
							@click="store.openPageInBrowser(store.activeApp!, store.activePage)"
						></FeatherIcon>
					</div>
				</template>
				<template #body="{ isOpen }">
					<div
						class="flex w-96 flex-col gap-3 rounded bg-white p-4 shadow-lg"
						v-if="store.activePage && store.activeApp"
					>
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

		<div class="absolute right-3 flex items-center gap-2">
			<Button
				size="sm"
				variant="subtle"
				:disabled="canvasStore.editingMode === 'fragment'"
				@click="() => store.openPageInBrowser(store.activeApp!, store.activePage!, true)"
			>
				Preview
			</Button>
			<Button
				size="sm"
				variant="solid"
				:disabled="canvasStore.editingMode === 'fragment'"
				:loading="publishing"
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
import { Tooltip, Popover } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"

import PageOptions from "@/components/PageOptions.vue"
import StudioLogo from "@/components/Icons/StudioLogo.vue"

import type { StudioMode } from "@/types"
import session from "@/utils/session"

const store = useStudioStore()
const canvasStore = useCanvasStore()
const publishing = ref(false)

const routeString = computed(() => store.activePage?.route || "/")
</script>
