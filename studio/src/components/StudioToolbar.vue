<template>
	<div
		class="toolbar flex h-14 items-center justify-center border-b border-outline-gray-2 bg-surface-base p-2"
	>
		<div class="absolute left-3 flex items-center justify-center gap-5">
			<Dropdown
				:options="[
					{
						group: 'Studio',
						hideLabel: true,
						options: [
							{
								label: 'Back to Dashboard',
								icon: 'lucide-arrow-left',
								onClick: () => $router.push({ name: 'Home' }),
							},
							{
								label: 'View in Desk',
								onClick: () => openInDesk(store.activeApp!),
								icon: 'lucide-arrow-up-right',
							},
							{
								label: 'App Settings',
								icon: 'lucide-settings',
								onClick: () => (showAppDialog = true),
							},
							{
								label: 'Studio Settings',
								icon: 'lucide-sliders-vertical',
								onClick: () => (store.showStudioSettingsDialog = true),
							},
							{
								label: 'Delete App',
								icon: 'lucide-trash-2',
								theme: 'red',
								onClick: () => store.deleteApp(store.activeApp?.app_name!, store.activeApp?.app_title!),
							},
						],
					},
					{
						group: 'More',
						hideLabel: true,
						options: [{ label: 'Logout', icon: 'lucide-log-out', onClick: () => session.logout() }],
					},
				]"
			>
				<template v-slot="{ open }">
					<div class="flex cursor-pointer items-center gap-1">
						<StudioLogo class="h-7 w-7"></StudioLogo>
						<component :is="open ? LucideChevronUp : LucideChevronDown" class="h-4 w-4 text-ink-gray-6" />
					</div>
				</template>
			</Dropdown>
			<ExportAppDialog v-if="canExportApp" v-model:showDialog="showExportAppDialog" />
			<div class="flex gap-2">
				<Tooltip
					:text="mode.description"
					:hoverDelay="600"
					v-for="mode in [
						{ mode: 'select', icon: 'lucide-mouse-pointer', description: 'Select (v)' },
						{ mode: 'container', icon: 'lucide-square', description: 'Container (c)' },
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
			<Popover v-model:open="store.showPageOptions" side="bottom" align="center" :offset="20" bare>
				<template #trigger>
					<div class="flex cursor-pointer items-center gap-2 p-2">
						<div class="flex h-6 items-center text-base text-ink-gray-7" v-if="!store.activePage">
							Loading...
						</div>
						<div v-else class="flex items-center gap-1">
							<span class="max-w-48 truncate text-base text-ink-gray-7">
								{{ store?.activePage?.page_title || "My Page" }}
							</span>
							-
							<span class="flex max-w-96 truncate text-base text-ink-gray-5">
								{{ routeString }}
							</span>
							<Tooltip
								v-if="!store.areRouteVariablesSet"
								text="Set route variable values here to preview page data"
							>
								<LucideCircleAlert class="h-[14px] w-[14px] text-ink-amber-5" />
							</Tooltip>
						</div>
						<LucideExternalLink
							v-if="store.activePage && store.activePage.published"
							class="h-[14px] w-[14px] !text-ink-gray-6 dark:!text-ink-gray-1"
							@click.stop="store.openPageInBrowser(store.activeApp!, store.activePage)"
						/>
					</div>
				</template>
				<template #default="{ open }">
					<div
						class="flex w-96 flex-col gap-3 rounded-4 bg-surface-base p-4 shadow-lg"
						v-if="store.activePage && store.activeApp"
					>
						<PageOptions
							v-if="store.activePage"
							:page="store.activePage"
							:app="store.activeApp"
							:isOpen="open"
						></PageOptions>
					</div>
				</template>
			</Popover>
		</div>

		<div class="absolute right-3 flex items-center gap-2">
			<Tooltip
				:text="store.activeApp?.is_standard ? 'App Export is enabled' : 'App Export Settings'"
				:hoverDelay="600"
				v-if="canExportApp"
			>
				<Button
					size="sm"
					variant="subtle"
					:icon="LucideArrowUpFromLine"
					label="Export App"
					@click="() => (showExportAppDialog = true)"
				/>
			</Tooltip>
			<Button
				size="sm"
				variant="subtle"
				@click="() => store.openPageInBrowser(store.activeApp!, store.activePage!, true)"
			>
				Preview
			</Button>
			<PublishButton :disabled="canvasStore.showFragmentCanvas" />
		</div>
		<AppDialog
			v-model:showDialog="showAppDialog"
			:app="store.activeApp"
			@update="(app: StudioApp) => store.setApp(app.name)"
		/>
		<StudioSettingsDialog v-model:showDialog="store.showStudioSettingsDialog" />
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Tooltip, Popover, Dropdown, Button } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"

import PageOptions from "@/components/PageOptions.vue"
import StudioLogo from "@/components/Icons/StudioLogo.vue"
import ExportAppDialog from "@/components/ExportAppDialog.vue"
import PublishButton from "@/components/PublishButton.vue"
import StudioSettingsDialog from "@/components/StudioSettingsDialog.vue"
import AppDialog from "@/components/AppDialog.vue"

import type { StudioMode } from "@/types"
import session from "@/utils/session"
import LucideArrowUpFromLine from "~icons/lucide/arrow-up-from-line"
import { isObjectEmpty, openInDesk } from "@/utils/helpers"
import { StudioApp } from "@/types/Studio/StudioApp"
import LucideChevronUp from "~icons/lucide/chevron-up"
import LucideChevronDown from "~icons/lucide/chevron-down"
import LucideCircleAlert from "~icons/lucide/circle-alert"
import LucideExternalLink from "~icons/lucide/external-link"

const store = useStudioStore()
const canvasStore = useCanvasStore()

const routeString = computed(() => store.activePage?.route || "/")
const showExportAppDialog = ref(false)
const canExportApp = computed(() => window.is_developer_mode && !isObjectEmpty(store.activeApp))

const showAppDialog = ref(false)
</script>
