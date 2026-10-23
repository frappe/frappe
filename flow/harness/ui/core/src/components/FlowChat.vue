<template>
	<!-- clip, not hidden: a hidden root still scrolls when focus lands in the closed panel.
	     The root is the sidebar's colour, so the chat stands on it as a raised panel -->
	<div
		class="flow-sidebar-surface flex h-full min-h-0 overflow-clip text-base text-ink-gray-8"
		:style="{
			'--flow-chat-text': `${store.state.prefs.chatFontSize}px`,
			'--flow-chat-weight': store.state.prefs.chatFontWeight,
		}"
	>
		<SessionSidebar :open="sidebarOpen" @close="store.setSidebarOpen(false)" />
		<div class="flex min-w-0 flex-1 overflow-clip bg-surface-base md:m-1 md:rounded-5 md:shadow-sm">
			<main class="relative flex min-w-0 flex-1 flex-col bg-surface-base">
				<ChatHeader :sidebar-open="sidebarOpen" @open-sidebar="store.setSidebarOpen(true)" />
				<MessageList ref="list" />
				<Composer ref="composer" />
			</main>
			<WorkspacePanel>
				<!-- the daemon's file views: the "+" menu, the editor and the picker -->
				<template #actions>
					<Dropdown class="flex-none" :options="addTabOptions">
						<template #trigger>
							<button class="flow-icon-btn" title="New tab">
								<FeatherIcon name="plus" class="h-3.5 w-3.5" />
							</button>
						</template>
					</Dropdown>
				</template>
				<template #view><EditorView /></template>
				<template #empty>
					<button
						class="flex w-44 items-center gap-2.5 rounded-6 border border-outline-gray-2 px-3 py-2.5 text-sm text-ink-gray-8 transition-colors hover:bg-surface-gray-1"
						@click="store.showFilesView()"
					>
						<FeatherIcon name="folder" class="h-4 w-4 flex-none text-ink-gray-5" />
						Files
					</button>
					<button
						class="flex w-44 items-center gap-2.5 rounded-6 border border-outline-gray-2 px-3 py-2.5 text-sm text-ink-gray-8 transition-colors hover:bg-surface-gray-1"
						@click="store.showDiffView()"
					>
						<FeatherIcon name="columns" class="h-4 w-4 flex-none text-ink-gray-5" />
						Diffs
					</button>
				</template>
			</WorkspacePanel>
		</div>

		<!-- host for frappe-ui's imperative dialog.* stack (confirm/danger/prompt) -->
		<Dialogs />
		<SettingsDialog v-model:tab="store.state.settingsTab" :groups="SETTINGS">
			<template #general><SettingsGeneral /></template>
			<template #appearance><SettingsAppearance /></template>
			<template #presets><SettingsPresets /></template>
			<template #skills><SettingsSkills /></template>
		</SettingsDialog>
		<TranscriptDialog />

		<Transition name="flow-toast">
			<div
				v-if="toast"
				class="fixed bottom-5 right-5 z-[9999] flex max-w-[360px] items-start gap-2 rounded-6 border border-outline-gray-2 bg-surface-base px-3.5 py-2.5 shadow-md max-md:inset-x-3 max-md:bottom-auto max-md:top-3 max-md:max-w-none"
			>
				<FeatherIcon
					:name="toast.kind === 'error' ? 'alert-circle' : 'info'"
					class="mt-1 h-3.5 w-3.5 flex-none"
					:class="toast.kind === 'error' ? 'text-ink-red-6' : 'text-ink-gray-5'"
				/>
				<span class="min-w-0 text-xs leading-relaxed text-ink-gray-8">{{ toast.message }}</span>
			</div>
		</Transition>
	</div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, provide, ref, watch } from "vue"
import Dialogs from "frappe-ui/src/components/Dialogs.vue"
import Dropdown from "frappe-ui/src/components/Dropdown/Dropdown.vue"
import { useColorScheme } from "frappe-ui/src/composables/useColorScheme"
import FeatherIcon from "./FeatherIcon.vue"

import { installShortcuts } from "../shortcuts.js"
import { installFocusRings } from "../focusRings.js"
import { installViewport } from "../viewport.js"
import { provideComposerHeight } from "../composerHeight.js"
import ChatHeader from "./ChatHeader.vue"
import Composer from "./Composer.vue"
import EditorView from "./EditorView.vue"
import MessageList from "./MessageList.vue"
import SessionSidebar from "./SessionSidebar.vue"
import SettingsAppearance from "./SettingsAppearance.vue"
import SettingsDialog from "./SettingsDialog.vue"
import SettingsGeneral from "./SettingsGeneral.vue"
import SettingsPresets from "./SettingsPresets.vue"
import SettingsSkills from "./SettingsSkills.vue"
import TranscriptDialog from "./TranscriptDialog.vue"
import WorkspacePanel from "./WorkspacePanel.vue"

const SETTINGS = [
	{
		label: "Settings",
		tabs: [
			{ id: "general", label: "General", icon: "settings" },
			{ id: "appearance", label: "Appearance", icon: "palette" },
			{ id: "presets", label: "Agent presets", icon: "layers" },
			{ id: "skills", label: "Skills", icon: "book-open" },
		],
	},
]

const props = defineProps({
	store: { type: Object, required: true },
})

provide("flow", props.store)
useColorScheme() // restores the saved theme and applies data-theme

// "+" menu: one entry per view the daemon's file system serves (browser, terminal later)
const addTabOptions = [
	{ label: "Files", icon: "lucide-folder", onClick: () => props.store.showFilesView() },
	{ label: "Diffs", icon: "lucide-file-diff", onClick: () => props.store.showDiffView() },
]

const sidebarOpen = computed(() => props.store.state.sidebarOpen)
const composer = ref(null)

provideComposerHeight(composer)
let uninstallShortcuts = null
let uninstallFocusRings = null
let uninstallViewport = null
onMounted(() => {
	uninstallShortcuts = installShortcuts(props.store)
	uninstallFocusRings = installFocusRings()
	uninstallViewport = installViewport()
})
onBeforeUnmount(() => {
	uninstallShortcuts?.()
	uninstallFocusRings?.()
	uninstallViewport?.()
})

const toast = ref(null)
let toastTimer = null
watch(
	() => props.store.state.toast,
	(t) => {
		if (!t) return
		toast.value = t
		clearTimeout(toastTimer)
		toastTimer = setTimeout(() => (toast.value = null), 4000)
	},
)

onMounted(async () => {
	props.store.refreshModels()
	props.store.refreshTools()
	await props.store.refreshSessions()
	// a refresh mid-session returns to that session, not to a blank chat
	const last = props.store.state.prefs.lastSession
	if (last && !props.store.state.sessionId && props.store.state.sessions.some((s) => s.session_id === last)) {
		props.store.openSession(last)
	}
})

onBeforeUnmount(() => props.store.detach())
</script>

<style scoped>
.flow-toast-enter-active,
.flow-toast-leave-active {
	transition:
		opacity 0.15s ease,
		transform 0.15s ease;
}
.flow-toast-enter-from,
.flow-toast-leave-to {
	opacity: 0;
	transform: translateY(6px);
}
/* a narrow frame's toast sits at the top, clear of the composer, and drops in from above */
@media (max-width: 767px) {
	.flow-toast-enter-from,
	.flow-toast-leave-to {
		transform: translateY(-6px);
	}
}
</style>
