<template>
	<Dialog v-model:open="store.showSettingsDialog" size="5xl" bare>
		<template #default="{ close }">
			<Dialog.Title class="sr-only">Settings</Dialog.Title>
			<Dialog.Description class="sr-only">Configure this app, its pages and the AI assistant.</Dialog.Description>
			<div class="flex h-[88vh] max-h-[min(800px,calc(100vh-6rem))] overflow-hidden">
				<div class="flex w-48 shrink-0 flex-col gap-5 bg-surface-gray-1 p-4 px-2">
					<span class="text-md-semibold px-2 text-ink-gray-9">Settings</span>
					<div class="flex flex-col gap-0.5">
						<Button
							v-for="tab in tabs"
							:key="tab.name"
							:variant="store.settingsTab === tab.name ? 'subtle' : 'ghost'"
							:icon-left="tab.icon"
							:class="{ '!bg-surface-gray-3': store.settingsTab === tab.name }"
							class="!justify-start"
							@click="store.settingsTab = tab.name"
						>
							{{ tab.label }}
						</Button>
					</div>
				</div>
				<div class="relative flex flex-1 flex-col gap-5 overflow-hidden bg-surface-base p-14 pl-16 pr-12 pb-0">
					<div class="flex flex-col gap-2">
						<h2 class="text-xl-semibold leading-none text-ink-gray-9">{{ activeTab.title }}</h2>
						<p v-if="activeTab.description" class="text-base text-ink-gray-5">{{ activeTab.description() }}</p>
					</div>
					<Button icon="lucide-x" variant="subtle" class="absolute right-5 top-5" @click="close" />
					<div class="min-h-0 flex-1 overflow-y-auto overscroll-contain pr-4">
						<component :is="activeTab.component" class="pb-16" />
					</div>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Button, Dialog } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import AppSettings from "@/components/Settings/AppSettings.vue"
import PagesSettings from "@/components/Settings/PagesSettings.vue"
import AISettings from "@/components/Settings/AISettings.vue"
import type { SettingsTab } from "@/types"

const store = useStudioStore()

type Tab = {
	name: SettingsTab
	label: string
	title: string
	description?: () => string | undefined
	icon: string
	component: object
}

const tabs: Tab[] = [
	{
		name: "app",
		label: "App",
		title: "App",
		description: () => store.activeApp?.app_name || store.activeApp?.name,
		icon: "lucide-app-window",
		component: AppSettings,
	},
	{ name: "pages", label: "Pages", title: "Pages", icon: "lucide-files", component: PagesSettings },
	{ name: "ai", label: "AI", title: "AI", icon: "lucide-sparkles", component: AISettings },
]

const activeTab = computed(() => tabs.find((tab) => tab.name === store.settingsTab) || tabs[0])
</script>
