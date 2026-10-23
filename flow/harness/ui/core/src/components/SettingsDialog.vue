<template>
	<!-- a narrow frame (a phone, a Desk panel) shows settings as a page: the sections in a list, each
	     opening as a page of its own with a way back -->
	<DialogRoot v-if="narrow" :open="flow.state.settingsOpen" @update:open="flow.setSettingsOpen($event)">
		<DialogPortal>
			<DialogContent
				:aria-describedby="undefined"
				class="flow-settings-page fixed inset-0 z-50 flex flex-col bg-surface-base focus:outline-none"
				@open-auto-focus.prevent
			>
				<header class="flex h-12 flex-none items-center px-2">
					<!-- a section's sub-page, like a record's form, leads back to the section -->
					<button
						v-if="section"
						class="flex h-9 items-center gap-0.5 rounded-6 pl-1 pr-2.5 text-ink-gray-8 hover:bg-surface-gray-2"
						@click="stepBack"
					>
						<FeatherIcon name="chevron-left" class="h-5 w-5" />
						<DialogTitle as="span" class="text-base">{{ back ? sectionLabel : "Settings" }}</DialogTitle>
					</button>
					<DialogTitle v-else class="px-2 text-base font-semibold text-ink-gray-9">Settings</DialogTitle>
					<span class="flex-1" />
					<DialogClose class="grid h-9 w-9 place-items-center rounded-6 text-ink-gray-7 hover:bg-surface-gray-2" title="Close">
						<FeatherIcon name="x" class="h-4 w-4" />
					</DialogClose>
				</header>
				<div class="relative min-h-0 flex-1 overflow-hidden">
					<Transition :name="forward ? 'flow-push' : 'flow-pop'">
						<div v-if="section" :key="section" class="absolute inset-0 flex flex-col bg-surface-base">
							<slot :name="section" />
						</div>
						<nav v-else class="absolute inset-0 overflow-y-auto bg-surface-base px-2 pb-6">
							<template v-for="(group, i) in groups" :key="i">
								<!-- one group is the page itself: its name would only repeat the title -->
								<div v-if="groups.length > 1" class="flex h-8 items-end px-3 pb-1 text-xs font-medium text-ink-gray-5" :class="i ? 'mt-3' : ''">
									{{ group.label }}
								</div>
								<button
									v-for="item in group.tabs"
									:key="item.id"
									class="flex h-12 w-full items-center gap-3 rounded-7 px-3 text-left text-base text-ink-gray-9 hover:bg-surface-gray-2 active:bg-surface-gray-2"
									@click="openSection(item.id)"
								>
									<FeatherIcon :name="item.icon" class="h-[18px] w-[18px] flex-none text-ink-gray-6" />
									<span class="min-w-0 flex-1 truncate">{{ item.label }}</span>
									<FeatherIcon name="chevron-right" class="h-4 w-4 flex-none text-ink-gray-4" />
								</button>
							</template>
						</nav>
					</Transition>
				</div>
			</DialogContent>
		</DialogPortal>
	</DialogRoot>

	<SettingsDialog
		v-else
		v-model:tab="active"
		size="6xl"
		:keyboard-shortcut="false"
		:open="flow.state.settingsOpen"
		@update:open="flow.setSettingsOpen($event)"
	>
		<SettingsSidebar class="pt-3">
			<SettingsNavGroup v-for="(group, i) in groups" :key="i">
				<template v-if="group.label" #label>
					<span class="mb-1 block text-2xs font-medium text-ink-gray-7">{{ group.label }}</span>
				</template>
				<SettingsNavItem v-for="item in group.tabs" :key="item.id" :value="item.id" class="text-xs">
					<template #prefix>
						<FeatherIcon :name="item.icon" class="h-4 w-4 text-ink-gray-6" />
					</template>
					{{ item.label }}
				</SettingsNavItem>
			</SettingsNavGroup>
		</SettingsSidebar>

		<!-- min-w-0 on the pane and each panel: long unbreakable content (paths)
		     must not widen them past the dialog -->
		<SettingsContent class="min-w-0">
			<SettingsPanel v-for="item in tabs" :key="item.id" :value="item.id" class="min-w-0">
				<slot :name="item.id" />
			</SettingsPanel>
		</SettingsContent>
	</SettingsDialog>
</template>

<script setup>
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue"
import { DialogClose, DialogContent, DialogPortal, DialogRoot, DialogTitle } from "reka-ui"
import {
	SettingsContent,
	SettingsDialog,
	SettingsNavGroup,
	SettingsNavItem,
	SettingsPanel,
	SettingsSidebar,
} from "frappe-ui/src/components/SettingsDialog"
import { dialogs } from "frappe-ui/src/utils/dialog"
import FeatherIcon from "./FeatherIcon.vue"

import { layout } from "../layout.js"
import { provideSettingsBack } from "../settingsBack.js"

// The settings shell: the dialog, its sidebar and its type scale are shared. A host
// names its tabs in `groups` and fills one slot per tab id with its own panel.
const props = defineProps({
	groups: { type: Array, required: true }, // [{ label, tabs: [{ id, label, icon }] }]
})
const tab = defineModel("tab", { type: String, default: undefined })
const flow = inject("flow")

const tabs = computed(() => props.groups.flatMap((group) => group.tabs))
const active = computed({
	get: () => tab.value ?? tabs.value[0]?.id,
	set: (value) => (tab.value = value),
})

// the page or the dialog, as the frame was when settings opened: a phone turned or a window resized
// mid-edit would swap the shell and unmount its editors, unsaved drafts and all
const narrow = ref(layout.narrow)

// the page's open section, null for the list. It opens on the list, or on the tab a caller asked
// for (a new preset), and forgets its section on closing, so the next open starts at the list.
const section = ref(null)
const sectionLabel = computed(() => tabs.value.find((item) => item.id === section.value)?.label)
const back = provideSettingsBack(narrow)
const forward = ref(true)
watch(
	() => flow.state.settingsOpen,
	(open) => {
		if (open) narrow.value = layout.narrow
		if (!narrow.value) return
		if (open) section.value = tab.value ?? null
		else tab.value = null
	},
)

// a phone's back goes back a screen, as the header's back does, and from the list closes settings.
// Each page and dialog is an entry in the browser's history, added only after a tap: Chrome's back
// skips all of a page's entries once it adds one with no tap since its last back. A frame's back is
// the page's around it, so a frame adds none.
const depth = computed(() =>
	flow.state.settingsOpen ? (narrow.value && section.value ? (back.value ? 3 : 2) : 1) + dialogs.value.length : 0,
)
let entries = window.history.state?.flowSettings ?? 0 // a reload keeps them, to leave
let tapped = false // since the last back
function syncHistory() {
	while (layout.phone && tapped && entries < depth.value && window.top === window)
		window.history.pushState({ ...window.history.state, flowSettings: ++entries }, "")
	if (entries > depth.value) window.history.go(depth.value - entries), (entries = depth.value)
}
// a frame that turns into a phone with settings open adds them then
watch([depth, () => layout.phone], syncHistory, { immediate: true })
function onPopState() {
	const had = entries
	entries = window.history.state?.flowSettings ?? 0
	tapped = false
	if (!had || entries >= depth.value) return
	if (dialogs.value.length) dialogs.value = dialogs.value.slice(0, -1)
	// a dialog the back opened has no entry, so entries can run out first: the last still closes settings
	else if (!entries) flow.setSettingsOpen(false)
	else stepBack()
}
// a screen left without its entry gets it on the next tap
function onTap() {
	tapped = true
	nextTick(syncHistory)
}
onMounted(() => {
	window.addEventListener("popstate", onPopState)
	window.addEventListener("click", onTap, true)
})
onBeforeUnmount(() => {
	window.removeEventListener("popstate", onPopState)
	window.removeEventListener("click", onTap, true)
})

// a sub-page's own back, else the section's, to the list
function stepBack() {
	if (back.value) back.value.go()
	else openSection(null)
}

function openSection(id) {
	forward.value = !!id
	section.value = id
	tab.value = id
}
</script>

<style scoped>
/* field labels read like the section titles next to them */
:deep([data-slot="label"]) {
	color: var(--ink-gray-9);
	font-weight: 500;
}
/* one step below frappe-ui's default control size, matching the panels' text */
:deep([data-slot="label"]),
:deep([data-slot="control"]),
:deep([data-slot="trigger"]) {
	font-size: 14px;
}

/* the page rises into place; a section slides in from the right over the list, and back out */
.flow-settings-page[data-state="open"] {
	animation: flow-page-in 0.25s cubic-bezier(0.32, 0.72, 0, 1);
}
.flow-settings-page[data-state="closed"] {
	animation: flow-page-out 0.15s ease-in;
}
@keyframes flow-page-in {
	from {
		opacity: 0;
		transform: translateY(24px);
	}
}
@keyframes flow-page-out {
	to {
		opacity: 0;
		transform: translateY(24px);
	}
}
.flow-push-enter-active,
.flow-push-leave-active,
.flow-pop-enter-active,
.flow-pop-leave-active {
	transition: transform 0.3s cubic-bezier(0.32, 0.72, 0, 1);
}
.flow-push-enter-from,
.flow-pop-leave-to {
	transform: translateX(100%);
}
.flow-push-leave-to,
.flow-pop-enter-from {
	transform: translateX(-25%);
}
/* the section is on top, coming or going */
.flow-push-enter-active,
.flow-pop-leave-active {
	z-index: 1;
}
@media (prefers-reduced-motion: reduce) {
	.flow-settings-page[data-state],
	.flow-push-enter-active,
	.flow-push-leave-active,
	.flow-pop-enter-active,
	.flow-pop-leave-active {
		animation: none;
		transition: none;
	}
}
</style>
