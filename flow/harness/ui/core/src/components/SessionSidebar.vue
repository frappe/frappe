<template>
	<Transition name="flow-backdrop">
		<button
			v-if="open"
			class="fixed inset-0 z-20 bg-black/30 md:hidden"
			aria-label="Close sidebar"
			@click="emit('close')"
		/>
	</Transition>
	<aside
		class="fixed inset-y-0 left-0 z-30 flex w-[var(--sidebar-w)] flex-none flex-col border-r border-outline-gray-1 bg-surface-sidebar md:relative"
		:class="[
			ready ? 'transition-[transform,margin-left] duration-200 ease-in-out' : '',
			// no transform while open: a transformed aside would become the containing
			// block for PopMenu's fixed backdrop, clipping it to the sidebar
			open ? '' : '-translate-x-full md:ml-[calc(-1*var(--sidebar-w))] md:translate-x-0',
		]"
		:style="{ '--sidebar-w': width + 'px' }"
	>
		<div class="flex h-12 items-center gap-2.5 px-3.5">
			<BrandMark :size="22" />
			<span class="text-sm font-semibold text-ink-gray-9">Flow</span>
			<span class="flex-1" />
			<button class="flow-icon-btn" title="Hide sidebar" @click="emit('close')">
				<FeatherIcon name="sidebar" class="h-3.5 w-3.5" />
			</button>
		</div>

		<div class="px-2.5 pb-1.5">
			<button
				class="flex h-9 w-full items-center gap-2 rounded-6 px-2.5 text-xs font-medium text-ink-gray-8 transition-colors hover:bg-surface-gray-2"
				@click="startNewChat"
			>
				<FeatherIcon name="plus" class="h-4 w-4 text-ink-gray-6" />
				New chat
			</button>
		</div>

		<div class="px-2.5 pb-1.5">
			<div
				class="flex h-8 items-center gap-2 rounded-5 border border-outline-gray-2 bg-surface-base px-2 text-ink-gray-5 transition-colors focus-within:border-outline-gray-3"
			>
				<FeatherIcon name="search" class="h-3.5 w-3.5 flex-none" />
				<input
					v-model="query"
					placeholder="Search chats"
					spellcheck="false"
					class="h-full w-full min-w-0 border-0 bg-transparent p-0 text-xs text-ink-gray-9 outline-none placeholder:text-ink-gray-4 focus:ring-0"
				/>
				<button
					v-if="query"
					class="grid h-4 w-4 flex-none place-items-center rounded-4 text-ink-gray-4 hover:text-ink-gray-8"
					title="Clear"
					@click="query = ''"
				>
					<FeatherIcon name="x" class="h-3 w-3" />
				</button>
			</div>
		</div>

		<div
			v-if="flow.state.sessions.length"
			class="flex items-center justify-between px-5 pb-1 pt-2 text-2xs font-medium text-ink-gray-5"
		>
			<span class="py-1">Sessions</span>
			<div v-if="projects.length" class="relative min-w-0">
				<button
					class="flex max-w-[128px] items-center gap-1 rounded-5 px-1.5 py-1 font-normal text-ink-gray-6 transition-colors hover:bg-surface-gray-2 hover:text-ink-gray-8"
					title="Filter sessions by project"
					aria-haspopup="menu"
					:aria-expanded="projectMenu"
					@click="projectMenu = !projectMenu"
				>
					<span class="truncate">{{ selectedProjectLabel }}</span>
					<FeatherIcon name="chevron-down" class="h-3 w-3 flex-none" />
				</button>
				<PopMenu
					:open="projectMenu"
					label="Filter sessions by project"
					align="right"
					placement="bottom"
					:width="220"
					@close="projectMenu = false"
				>
					<button
						role="menuitemradio"
						:aria-checked="selectedProject === null"
						class="flex w-full items-center gap-2 rounded-5 px-2.5 py-2 text-left text-xs text-ink-gray-8 hover:bg-surface-gray-2"
						@click="selectProject(null)"
					>
						<FeatherIcon name="folder" class="h-3.5 w-3.5 flex-none text-ink-gray-5" />
						<span class="min-w-0 flex-1 truncate">All projects</span>
						<FeatherIcon v-if="selectedProject === null" name="check" class="h-3.5 w-3.5 flex-none" />
					</button>
					<button
						v-for="project in projects"
						:key="project.cwd"
						role="menuitemradio"
						:aria-checked="selectedProject === project.cwd"
						:title="project.cwd"
						class="flex w-full items-center gap-2 rounded-5 px-2.5 py-2 text-left text-xs text-ink-gray-8 hover:bg-surface-gray-2"
						@click="selectProject(project.cwd)"
					>
						<FeatherIcon name="folder" class="h-3.5 w-3.5 flex-none text-ink-gray-5" />
						<span class="min-w-0 flex-1 truncate">{{ project.name }}</span>
						<FeatherIcon
							v-if="selectedProject === project.cwd"
							name="check"
							class="h-3.5 w-3.5 flex-none"
						/>
					</button>
				</PopMenu>
			</div>
		</div>

		<div class="flex flex-1 flex-col gap-0.5 overflow-y-auto px-2.5 pb-2.5">
			<div
				v-for="s in filtered"
				:key="s.session_id"
				role="button"
				tabindex="0"
				class="group relative flex cursor-pointer items-center rounded-6 px-2.5 py-2 hover:bg-surface-gray-2 focus-visible:bg-surface-gray-2 focus-visible:outline-none"
				:class="[
					s.session_id === flow.state.sessionId ? 'bg-surface-gray-3' : '',
					menuFor === s.session_id ? 'menu-open bg-surface-gray-2' : '',
				]"
				@click="flow.openSession(s.session_id)"
				@keydown.enter.prevent="flow.openSession(s.session_id)"
				@keydown.space.prevent="flow.openSession(s.session_id)"
			>
				<span
					class="session-title block min-w-0 w-full truncate text-xs leading-snug"
					:class="s.session_id === flow.state.sessionId ? 'font-medium text-ink-gray-9' : 'text-ink-gray-8'"
				>
					{{ flow.sessionTitle(s) }}
				</span>
				<span
					class="absolute right-2 top-1/2 grid h-5 w-5 -translate-y-1/2 place-items-center text-2xs text-ink-gray-5 transition-opacity group-hover:opacity-0"
					:class="menuFor === s.session_id ? 'opacity-0' : ''"
				>
					<span
						v-if="s.state === 'running'"
						class="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-surface-green-7"
						title="Running"
					/>
					<span v-else-if="s.state === 'paused'" title="Waiting for approval">⏸</span>
				</span>
				<Dropdown
					align="end"
					:options="sessionActions(s)"
					:open="menuFor === s.session_id"
					@update:open="(open) => (menuFor = open ? s.session_id : null)"
				>
					<template #trigger>
						<button
							class="absolute right-1 top-1/2 z-10 grid h-7 w-7 -translate-y-1/2 place-items-center rounded-5 text-ink-gray-5 transition-[color,background-color,opacity] hover:bg-surface-gray-4 hover:text-ink-gray-8 focus-visible:bg-surface-gray-4 focus-visible:opacity-100"
							:class="
								menuFor === s.session_id
									? 'bg-surface-gray-4 text-ink-gray-8 opacity-100'
									: 'bg-transparent opacity-0 group-hover:opacity-100'
							"
							title="Session options"
							@click.stop
							@keydown.enter.stop
							@keydown.space.stop
						>
							<FeatherIcon name="more-horizontal" class="h-[13px] w-[13px]" />
						</button>
					</template>
				</Dropdown>
			</div>
			<div v-if="filtered.length === 0" class="px-2.5 py-8 text-center text-xs text-ink-gray-5">
				{{ emptyMessage }}
			</div>
			<div
				v-if="flow.state.sessionsMore"
				ref="sentinel"
				class="px-2.5 py-2 text-center text-2xs text-ink-gray-4"
			>
				Loading more…
			</div>
		</div>

		<div
			class="absolute inset-y-0 right-0 z-10 hidden w-1 cursor-col-resize hover:bg-[--outline-gray-2] active:bg-[--outline-gray-3] md:block"
			title="Drag to resize · double-click to reset"
			@pointerdown="startResize"
			@dblclick="resetWidth"
		/>

		<footer class="border-t border-outline-gray-1 px-2.5 py-1.5">
			<button
				class="flex h-9 w-full items-center gap-2 rounded-6 px-2.5 text-xs font-medium text-ink-gray-8 transition-colors hover:bg-surface-gray-2"
				@click="flow.setSettingsOpen(true)"
			>
				<FeatherIcon name="settings" class="h-4 w-4 text-ink-gray-6" />
				Settings
			</button>
		</footer>
	</aside>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from "vue"
import Dropdown from "frappe-ui/src/components/Dropdown/Dropdown.vue"
import FeatherIcon from "./FeatherIcon.vue"

import { dialog } from "frappe-ui/src/utils/dialog"

import { useDebouncedValue } from "../debounce.js"
import BrandMark from "./BrandMark.vue"
import PopMenu from "./PopMenu.vue"

const props = defineProps({ open: { type: Boolean, default: true } })
const emit = defineEmits(["close"])
const flow = inject("flow")

const query = ref("")
const debouncedQuery = useDebouncedValue(query, 150)
watch(debouncedQuery, (q) => flow.searchSessions(q))

// the row under the last session: scrolling it into view asks for the next page
const sentinel = ref(null)
let observer = null
onMounted(() => {
	if (typeof IntersectionObserver === "undefined") return
	observer = new IntersectionObserver((entries) => {
		if (entries.some((entry) => entry.isIntersecting)) flow.loadMoreSessions()
	})
	if (sentinel.value) observer.observe(sentinel.value)
})
watch(sentinel, (el, old) => {
	if (old) observer?.unobserve(old)
	if (el) observer?.observe(el)
})
onBeforeUnmount(() => observer?.disconnect())
const projectMenu = ref(false)
const selectedProject = ref(null)
const menuFor = ref(null)

function projectName(cwd) {
	return cwd.replace(/[\\/]+$/, "").split(/[\\/]/).filter(Boolean).pop() ?? cwd
}

const projects = computed(() => {
	const unique = new Map()
	for (const session of flow.state.sessions) {
		const cwd = session.cwd?.trim()
		if (cwd && !unique.has(cwd)) unique.set(cwd, { cwd, name: projectName(cwd) })
	}
	return [...unique.values()].sort((left, right) => left.name.localeCompare(right.name))
})

const selectedProjectLabel = computed(() =>
	selectedProject.value ? projectName(selectedProject.value) : "All projects",
)

function selectProject(cwd) {
	selectedProject.value = cwd
	projectMenu.value = false
}

function startNewChat() {
	flow.startNewChat({ cwd: selectedProject.value })
}

watch(projects, (available) => {
	if (selectedProject.value && !available.some((project) => project.cwd === selectedProject.value)) {
		selectedProject.value = null
	}
})

function sessionActions(s) {
	return [
		{ label: "Rename", icon: "lucide-pen", onClick: () => promptRename(s) },
		{ label: "Delete", icon: "lucide-trash-2", theme: "red", onClick: () => confirmDelete(s) },
	]
}

function promptRename(s) {
	dialog.prompt({
		title: "Rename chat",
		fields: [{ name: "title", label: "Name", defaultValue: flow.sessionTitle(s), required: true }],
		confirmLabel: "Rename",
		// fire-and-forget (outcome lands as a toast): returning the promise would
		// flash the button's loading state for ~20ms and jolt the action row
		onConfirm: ({ values }) => {
			void flow.renameSession(s.session_id, values.title.trim())
		},
	})
}

// dialog.confirm, not dialog.danger: danger's red theme injects a header
// icon; the destructive styling lives on the action button instead
function confirmDelete(s) {
	dialog.confirm({
		title: "Delete chat?",
		message: `“${flow.sessionTitle(s)}” and its full history will be permanently removed.`,
		actions: [
			{ label: "Cancel", variant: "outline" },
			{
				label: "Delete",
				variant: "solid",
				theme: "red",
				onClick: () => {
					void flow.deleteSession(s.session_id)
				},
			},
		],
	})
}

const DEFAULT_WIDTH = 288
const clampWidth = (w) => Math.min(420, Math.max(224, w))
const width = ref(clampWidth(flow.state.prefs.sidebarWidth ?? DEFAULT_WIDTH))

function resetWidth() {
	width.value = DEFAULT_WIDTH
	flow.setSidebarWidth(DEFAULT_WIDTH)
}

function startResize(event) {
	event.preventDefault()
	const handle = event.currentTarget
	handle.setPointerCapture(event.pointerId)
	const startX = event.clientX
	const startWidth = width.value
	const move = (e) => (width.value = clampWidth(startWidth + e.clientX - startX))
	const up = (e) => {
		handle.releasePointerCapture(e.pointerId)
		handle.removeEventListener("pointermove", move)
		handle.removeEventListener("pointerup", up)
		flow.setSidebarWidth(width.value)
	}
	handle.addEventListener("pointermove", move)
	handle.addEventListener("pointerup", up)
}

// enable the slide transition only after mount, so a closed saved state
// doesn't animate on page load
const ready = ref(false)
onMounted(() => requestAnimationFrame(() => (ready.value = true)))

const filtered = computed(() => {
	const q = debouncedQuery.value.trim().toLowerCase()
	return flow.state.sessions.filter((session) => {
		if (selectedProject.value && session.cwd !== selectedProject.value) return false
		return !q || flow.sessionTitle(session).toLowerCase().includes(q)
	})
})

const emptyMessage = computed(() => {
	if (query.value) return "No matches."
	if (selectedProject.value) return "No chats in this project."
	return "No chats yet — start one."
})
</script>

<style scoped>
.flow-backdrop-enter-active,
.flow-backdrop-leave-active {
	transition: opacity 0.2s ease;
}
.flow-backdrop-enter-from,
.flow-backdrop-leave-to {
	opacity: 0;
}

/* reka copies the content's z-index onto its fixed popper wrapper; without
   this the menu paints under the z-30 sidebar */
:global(.dropdown-content) {
	z-index: 40;
}

.group:hover .session-title,
.group:focus-within .session-title,
.group.menu-open .session-title {
	-webkit-mask-image: linear-gradient(to right, #000 calc(100% - 3rem), transparent calc(100% - 1.5rem));
	mask-image: linear-gradient(to right, #000 calc(100% - 3rem), transparent calc(100% - 1.5rem));
}
</style>
