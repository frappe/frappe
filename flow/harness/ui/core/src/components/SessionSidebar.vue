<template>
	<!-- only once the script knows the frame is narrow: a wide frame turning narrow draws first -->
	<Transition name="flow-backdrop">
		<button
			v-if="open && layout.narrow"
			class="fixed inset-0 z-20 bg-black/30 md:hidden"
			aria-label="Close sidebar"
			@click="emit('close')"
		/>
	</Transition>
	<aside
		class="flow-sidebar-surface fixed inset-y-0 left-0 z-30 flex w-[var(--sidebar-w)] flex-none flex-col md:relative"
		:class="[
			sliding ? 'transition-[transform,margin-left] duration-200 ease-in-out' : '',
			// no transform while open: a transformed aside would become the containing
			// block for a menu's fixed backdrop, clipping it to the sidebar. Open in a wide
			// frame that just turned narrow, it hides until the script closes it
			open
				? layout.narrow ? '' : 'max-md:-translate-x-full'
				: '-translate-x-full md:ml-[calc(-1*var(--sidebar-w))] md:translate-x-0',
			dragging && 'flow-reordering',
		]"
		:style="{ '--sidebar-w': layout.phone ? 'min(85vw, 360px)' : width + 'px' }"
		:inert="!open"
	>
		<div class="flex h-12 flex-none items-center gap-2.5 pl-3.5 pr-2">
			<BrandMark :size="22" />
			<span class="text-sm font-semibold text-ink-gray-9">Flow</span>
			<span class="flex-1" />
			<button class="flow-icon-btn" title="Hide sidebar" @click="emit('close')">
				<FeatherIcon name="sidebar" class="h-3.5 w-3.5" />
			</button>
		</div>

		<!-- 7px over, 9px under: New chat sits midway between the brand mark and the list's header;
		     it and the header (or search) are as tall as a workspace row -->
		<div class="mt-[7px] flex flex-none flex-col gap-0.5 px-2">
			<SidebarItem icon="lucide-square-pen" class="h-8" @click="startNewChat()">
				<span class="truncate text-xs font-medium text-ink-gray-8">New chat</span>
			</SidebarItem>
			<!-- the host's own rows, like links to its pages -->
			<slot name="nav" />
		</div>

		<!-- outside the scroller, so search stays in reach down a long list -->
		<div v-if="flow.state.sessions.length || flow.state.folders?.length || searchOpen" class="list-head mt-[9px] flex h-8 flex-none items-center gap-0.5 px-2">
			<!-- 4px short of the header and at its top, so the field stands clear of the first row -->
			<label
				v-if="searchOpen"
				class="flex h-[calc(100%-4px)] min-w-0 flex-1 items-center gap-1.5 self-start rounded-4 bg-surface-base pl-2.5 pr-0.5"
			>
				<span class="lucide-search size-4 flex-none text-ink-gray-5" aria-hidden="true" />
				<input
					ref="searchInput"
					v-model="query"
					placeholder="Search chats"
					aria-label="Search chats"
					spellcheck="false"
					class="h-full min-w-0 flex-1 border-0 bg-transparent p-0 text-xs text-ink-gray-9 outline-none placeholder:text-ink-gray-4 focus:ring-0"
					@keydown.esc="closeSearch"
					@blur="query || closeSearch()"
				/>
				<button
					class="grid h-full w-6 flex-none place-items-center text-ink-gray-5 hover:text-ink-gray-8"
					title="Close search"
					@click="closeSearch"
				>
					<span class="lucide-x size-3.5" aria-hidden="true" />
				</button>
			</label>
			<template v-else>
				<h3 class="min-w-0 flex-1 truncate pl-2 text-xs font-medium text-ink-gray-5">
					{{ grouped ? "Workspaces" : "Sessions" }}
				</h3>
				<button
					class="grid size-7 flex-none place-items-center rounded-4 text-ink-gray-5 transition-colors hover:bg-surface-gray-3 hover:text-ink-gray-7"
					title="Search chats"
					@click="openSearch"
				>
					<span class="lucide-search size-4" aria-hidden="true" />
				</button>
				<Dropdown v-if="hasWorkspaces" align="end" :options="viewOptions">
					<template #trigger>
						<button
							class="grid size-7 flex-none place-items-center rounded-4 text-ink-gray-5 transition-colors hover:bg-surface-gray-3 hover:text-ink-gray-7 data-[state=open]:bg-surface-gray-3 data-[state=open]:text-ink-gray-7"
							title="Group and sort"
						>
							<span class="lucide-sliders-horizontal size-4" aria-hidden="true" />
						</button>
					</template>
				</Dropdown>
				<button
					v-if="hasWorkspaces"
					class="grid size-7 flex-none place-items-center rounded-4 text-ink-gray-5 transition-colors hover:bg-surface-gray-3 hover:text-ink-gray-7"
					title="New workspace"
					@click="newWorkspace"
				>
					<span class="lucide-folder-plus size-4" aria-hidden="true" />
				</button>
			</template>
		</div>

		<div class="flex min-h-0 flex-1 flex-col overflow-y-auto px-2 pb-2 pt-0.5">
			<!-- one wrapper for the rows: as children of the scroller they would shrink to fit -->
			<div class="flex flex-col gap-0.5">
				<template v-for="group in groups" :key="group.cwd ?? ''">
					<!-- the new-chat button floats over the row's end, so a click anywhere else on the row folds it -->
					<SidebarItem
						v-if="group.cwd"
						class="group relative h-8 select-none"
						:class="[
							dragClass(group.cwd),
							menuFor === group.cwd && 'menu-open bg-surface-gray-2',
							flow.state.folders && !layout.phone && 'workspace-menu',
						]"
						:aria-expanded="group.open"
						:data-reorder="canReorder ? 'folder' : null"
						:data-key="group.cwd"
						@click="toggleWorkspace(group.cwd)"
						@pointerdown.capture="holdCard(group.cwd)"
						@pointerdown="pressStart(group.cwd, $event); dragStart('folder', group.cwd, $event)"
						@pointerup="pressEnd"
						@pointercancel="pressEnd"
						@pointerleave="pressEnd(); releaseCard(group.cwd)"
					>
						<template #prefix>
							<span
								class="size-4 text-ink-gray-6"
								:class="group.open ? 'lucide-folder-open' : 'lucide-folder'"
								aria-hidden="true"
							/>
						</template>
						<HoverCard
							side="right"
							:offset="12"
							:hover-delay="500"
							:leave-delay="0"
							:open="cardFor === group.cwd"
							@update:open="(open) => showCard(group.cwd, open)"
						>
							<template #trigger>
								<span class="row-title folder-name min-w-0 flex-1 overflow-hidden whitespace-nowrap text-xs leading-snug text-ink-gray-8">
									{{ group.name }}
								</span>
							</template>
							<!-- no wider than the room beside the row, which a narrow window's drawer cuts short -->
							<div class="row-card flex max-w-[min(20rem,var(--reka-hover-card-content-available-width,20rem))] flex-col gap-1.5 px-3 py-2.5">
								<p class="break-words text-sm leading-snug text-ink-gray-8">{{ group.name }}</p>
								<p class="flex items-start gap-1.5 text-xs leading-4 text-ink-gray-6">
									<span class="lucide-folder size-4 flex-none text-ink-gray-5" aria-hidden="true" />
									<span class="break-all">{{ group.cwd }}</span>
								</p>
							</div>
						</HoverCard>
						<!-- its menu, then a new chat; a phone's row shows no buttons: a long press opens
						     its menu, from where they sit -->
						<template #suffix>
							<Dropdown
								v-if="layout.phone || flow.state.folders"
								align="end"
								:options="workspaceOptions(group)"
								:open="menuFor === group.cwd"
								@update:open="(open) => setMenu(group.cwd, open)"
							>
								<template #trigger>
									<span v-if="layout.phone" class="row-action absolute right-1 top-1/2 size-5 -translate-y-1/2" />
									<button
										v-else
										class="row-action absolute right-8 top-1/2 grid size-6 -translate-y-1/2 place-items-center rounded-4 text-ink-gray-5 hover:bg-surface-gray-4 hover:text-ink-gray-8"
										:class="menuFor === group.cwd ? 'text-ink-gray-7' : 'flow-hover-reveal'"
										title="Workspace options"
										@pointerdown.stop
									>
										<span class="lucide-ellipsis size-4" aria-hidden="true" />
									</button>
								</template>
							</Dropdown>
							<button
								v-if="!layout.phone"
								class="row-action flow-hover-reveal absolute right-0.5 top-1/2 grid size-6 -translate-y-1/2 place-items-center rounded-4 text-ink-gray-5 hover:bg-surface-gray-4 hover:text-ink-gray-8"
								:title="`New chat in ${group.name}`"
								@click="startNewChat(group.cwd)"
								@pointerdown.stop
							>
								<span class="lucide-square-pen size-4" aria-hidden="true" />
							</button>
						</template>
					</SidebarItem>
					<h3 v-else-if="grouped" class="flex h-7 items-center pl-2 text-2xs font-medium text-ink-gray-5">
						Ungrouped
					</h3>
					<!-- while a workspace is dragged only the workspaces show, so it drops between them -->
					<Transition name="flow-fold">
						<div v-if="group.open && dragging?.scope !== 'folder'" class="flow-fold" :class="group.cwd && '-mt-px'">
							<!-- chats sit 30px apart, the first 31px under its workspace's name; 34px
							     apart in one list, which has no names to space against. A phone's
							     taller rows keep the 2px gaps -->
							<div class="grid min-h-0 grid-cols-1" :class="grouped || layout.phone ? 'gap-0.5' : 'gap-1.5'">
								<SidebarItem
									v-for="s in group.chats"
									:key="s.session_id"
									:label="flow.sessionTitle(s)"
									class="group relative h-7 select-none data-[state=active]:bg-surface-gray-3 data-[state=active]:shadow-none data-[state=inactive]:text-ink-gray-8"
									:class="[!grouped && 'quiet', menuFor === s.session_id && 'menu-open bg-surface-gray-2', dragClass(s.session_id)]"
									:active="chatInView && s.session_id === flow.state.sessionId"
									:data-reorder="canReorder ? `chat:${group.cwd ?? ''}` : null"
									:data-key="s.session_id"
									@click="pick(s)"
									@pointerdown.capture="holdCard(s.session_id)"
									@pointerdown="pressStart(s.session_id, $event); dragStart(`chat:${group.cwd ?? ''}`, s.session_id, $event)"
									@pointerup="pressEnd"
									@pointercancel="pressEnd"
									@pointerenter="crawlTitle"
									@pointerleave="pressEnd(); restTitle($event); releaseCard(s.session_id)"
								>
									<!-- an empty icon lane lines a workspace's chats up under its name; loose chats line up with the label -->
									<template v-if="group.cwd" #prefix><span class="size-4" /></template>
									<HoverCard
										side="right"
										:offset="12"
										:hover-delay="500"
										:leave-delay="0"
										:open="cardFor === s.session_id"
										@update:open="(open) => showCard(s.session_id, open)"
									>
										<template #trigger>
											<span
												class="row-title min-w-0 flex-1 overflow-hidden whitespace-nowrap text-xs leading-snug"
												:class="!group.cwd && '-ml-2'"
											>
												<span class="inline-block">{{ flow.sessionTitle(s) }}</span>
											</span>
										</template>
										<div class="row-card flex max-w-[min(20rem,var(--reka-hover-card-content-available-width,20rem))] flex-col gap-1.5 px-3 py-2.5">
											<p class="break-words text-sm leading-snug text-ink-gray-8">{{ flow.sessionTitle(s) }}</p>
											<p v-if="s.cwd" class="flex items-center gap-1.5 text-xs text-ink-gray-6">
												<span class="lucide-folder size-4 flex-none text-ink-gray-5" aria-hidden="true" />
												<span class="truncate">{{ flow.folderName(s.workspace ?? s.cwd) }}</span>
											</p>
										</div>
									</HoverCard>
									<template #suffix>
										<ChatMenu
											:session-id="s.session_id"
											:title="flow.sessionTitle(s)"
											:open="menuFor === s.session_id"
											@update:open="(open) => setMenu(s.session_id, open)"
										>
											<button
												class="row-action chat-options absolute right-0.5 top-1/2 z-10 grid size-6 -translate-y-1/2 place-items-center rounded-4 text-ink-gray-5 transition-[color,opacity] hover:bg-surface-gray-4 hover:text-ink-gray-8"
												:class="menuFor === s.session_id ? 'text-ink-gray-7 opacity-100' : 'opacity-0 group-hover:opacity-100'"
												title="Session options"
												@pointerdown.stop
											>
												<span class="lucide-ellipsis size-4" aria-hidden="true" />
											</button>
										</ChatMenu>
									</template>
								</SidebarItem>
								<SidebarItem v-if="group.toggle" :label="group.toggle" @click="toggleShowAll(group.cwd)">
									<template #prefix><span class="size-4" /></template>
									<span class="text-xs leading-snug text-ink-gray-5">{{ group.toggle }}</span>
								</SidebarItem>
							</div>
						</div>
					</Transition>
				</template>
			</div>
			<LoadingState
				v-if="filtered.length === 0 && flow.state.sessionsLoading"
				class="justify-center px-2.5 py-8 text-xs text-ink-gray-5"
			/>
			<div v-else-if="filtered.length === 0" class="px-2.5 py-8 text-center text-xs text-ink-gray-5">
				{{ emptyMessage }}
			</div>
			<button
				v-if="flow.state.sessionsMore"
				ref="sentinel"
				type="button"
				class="w-full px-2.5 py-2 text-center text-2xs text-ink-gray-4 hover:text-ink-gray-6"
				:disabled="flow.state.sessionsLoading"
				@click="flow.loadMoreSessions()"
			>
				{{ flow.state.sessionsLoading ? "Loading more…" : "Load more" }}
			</button>
		</div>

		<!-- in the 4px gap beside the raised chat panel, so its bar fills that gap -->
		<div
			class="absolute inset-y-0 -right-1 z-10 hidden w-1 cursor-col-resize hover:bg-[--outline-gray-2] active:bg-[--outline-gray-3] md:block"
			title="Drag to resize · double-click to reset"
			@pointerdown="startResize"
			@dblclick="resetWidth"
		/>

		<footer class="flex flex-col gap-0.5 border-t border-outline-gray-1 p-2">
			<SidebarItem icon="lucide-settings" @click="flow.setSettingsOpen(true)">
				<span class="truncate text-xs font-medium text-ink-gray-8">Settings</span>
			</SidebarItem>
		</footer>
	</aside>
</template>

<script setup>
import { computed, h, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue"
import Dropdown from "frappe-ui/src/components/Dropdown/Dropdown.vue"
import HoverCard from "frappe-ui/src/components/HoverCard/HoverCard.vue"
import SidebarItem from "frappe-ui/src/components/Sidebar/SidebarItem.vue"
import { dialog } from "frappe-ui/src/utils/dialog"
import FeatherIcon from "./FeatherIcon.vue"

import { useDebouncedValue } from "../debounce.js"
import { layout, useSlide } from "../layout.js"
import BrandMark from "./BrandMark.vue"
import ChatMenu from "./ChatMenu.vue"
import LoadingState from "./LoadingState.vue"

// chatInView: false while a host shows a page in the open chat's place, so no chat row is marked.
// beforeSwitch: such a host's say before a pick changes the open chat, resolving false to keep it
const props = defineProps({
	open: { type: Boolean, default: true },
	chatInView: { type: Boolean, default: true },
	beforeSwitch: { type: Function, default: null },
})
const emit = defineEmits(["close"])
const flow = inject("flow")

const query = ref("")
const debouncedQuery = useDebouncedValue(query, 150)
watch(debouncedQuery, (q) => flow.searchSessions(q))

const searchOpen = ref(false)
const searchInput = ref(null)
function openSearch() {
	searchOpen.value = true
	nextTick(() => searchInput.value?.focus())
}
function closeSearch() {
	query.value = ""
	searchOpen.value = false
}

// the row under the last session: scrolling it into view asks for the next page, and a
// click asks again after a page that failed
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
const menuFor = ref(null)

// a row's card (a chat's id, a workspace's folder) shows after a hover dwell, never beside
// an open menu or during a drag; a press anywhere on its row (a click, its buttons, a drag)
// puts it away until the pointer leaves the row
const cardFor = ref(null)
let cardHeld = null
function showCard(key, open) {
	if (open && !menuFor.value && !dragging.value && cardHeld !== key) cardFor.value = key
	else if (cardFor.value === key) cardFor.value = null
}
function holdCard(key) {
	cardHeld = key
	cardFor.value = null
}
function releaseCard(key) {
	if (cardHeld === key) cardHeld = null
}
function setMenu(key, open) {
	menuFor.value = open ? key : null
	cardFor.value = null
}

// a workspace's menu: Rename and Delete where the daemon keeps workspaces, after New chat on a
// phone, whose rows show no buttons
function workspaceOptions(group) {
	const own = flow.state.folders
		? [
				{ label: "Rename", icon: "lucide-pen", onClick: () => promptRename(group) },
				{ label: "Delete", icon: "lucide-trash-2", theme: "red", onClick: () => confirmDelete(group) },
			]
		: []
	if (!layout.phone) return own
	return [{ label: "New chat", icon: "lucide-square-pen", onClick: () => startNewChat(group.cwd) }, ...own]
}

// each dialog keeps the workspace it was opened for
function promptRename({ cwd, name }) {
	dialog.prompt({
		title: "Rename workspace",
		size: "lg",
		fields: [{ name: "name", label: "Name", defaultValue: name, required: true }],
		confirmLabel: "Rename",
		onConfirm: ({ values }) => {
			void flow.renameFolder(cwd, values.name.trim())
		},
	})
}

function confirmDelete({ cwd, name }) {
	dialog.confirm({
		title: "Delete workspace?",
		size: "lg",
		message: `“${name}” leaves the sidebar. Its folder and chats are kept, and the chats move to Ungrouped.`,
		actions: [
			{ label: "Cancel", variant: "outline" },
			{
				label: "Delete",
				variant: "solid",
				theme: "red",
				onClick: () => {
					void flow.removeFolder(cwd)
				},
			},
		],
	})
}

// a long chat title crawls left at reading speed while its row is hovered, until its end
// shows clear of the row's ••• (the hover fade starts 3rem from the end); leaving puts it back
const CRAWL_PX_PER_S = 30
let crawlTimer = null
function crawlTitle(event) {
	clearTimeout(crawlTimer)
	if (event.pointerType !== "mouse" || dragging.value) return
	const title = event.currentTarget.querySelector(".row-title")
	crawlTimer = setTimeout(() => {
		const rem = parseFloat(getComputedStyle(document.documentElement).fontSize)
		const range = title.firstElementChild.offsetWidth - (title.clientWidth - 3 * rem)
		if (range < 8) return // a few pixels of travel reads as jitter
		title.style.setProperty("--crawl", `${-range}px`)
		title.style.setProperty("--crawl-time", `${range / CRAWL_PX_PER_S}s`)
		title.dataset.crawl = ""
	}, 300)
}
function restTitle(event) {
	clearTimeout(crawlTimer)
	delete event.currentTarget.querySelector(".row-title")?.dataset.crawl
}
onBeforeUnmount(() => clearTimeout(crawlTimer))

const CHATS_SHOWN = 5
const searching = computed(() => !!debouncedQuery.value.trim())
const showingAll = ref([]) // workspaces listing all their chats, by folder
const hasWorkspaces = computed(() => !!flow.state.folders || flow.state.sessions.some((session) => session.cwd?.trim()))
const grouped = computed(() => hasWorkspaces.value && flow.state.prefs.sidebarGroup !== "list")
const manual = computed(() => flow.state.prefs.sidebarOrder === "manual")
// rows drag only where the filters menu shows, so the order can be set back, and over the
// whole list, since a drop saves every chat's place
const canReorder = computed(
	() => hasWorkspaces.value && !searching.value && !flow.state.sessionsMore && !flow.state.sessionQuery,
)

// the filters menu, its current choices ticked
const tick = () => h("span", { class: "lucide-check ml-auto size-4 text-ink-gray-7", "aria-hidden": "true" })
const viewOptions = computed(() => {
	const option = (label, icon, chosen, view) => ({
		label,
		icon,
		slots: chosen ? { suffix: tick } : {},
		onClick: () => flow.setSidebarView(view),
	})
	return [
		{
			group: "Group by",
			options: [
				option("Workspace", "lucide-folder", grouped.value, { sidebarGroup: "workspace" }),
				option("In one list", "lucide-list", !grouped.value, { sidebarGroup: "list" }),
			],
		},
		{
			group: "Order by",
			options: [
				option("Manual", "lucide-chevrons-up-down", manual.value, { sidebarOrder: "manual" }),
				option("Last updated", "lucide-clock", !manual.value, { sidebarOrder: "updated" }),
			],
		},
	]
})

// items in a saved manual order; ones it hasn't placed yet go first, in the order given
function arrange(items, order = [], keyOf = (item) => item) {
	const place = new Map(order.map((key, i) => [key, i]))
	return [...items].sort((a, b) => (place.get(keyOf(a)) ?? -1) - (place.get(keyOf(b)) ?? -1))
}

// chats by workspace, each workspace by its latest chat, after the daemon's with no chats
// yet, newest first, unless `empty` is off; chats in none are loose
function byWorkspace(chats, empty = true) {
	const kept = flow.state.folders && new Set(flow.state.folders.map((folder) => folder.path))
	const workspaces = new Map()
	const loose = []
	for (const session of chats) {
		const cwd = kept ? session.workspace : session.cwd?.trim()
		if (!cwd || (kept && !kept.has(cwd))) loose.push(session)
		else if (workspaces.has(cwd)) workspaces.get(cwd).chats.push(session)
		else workspaces.set(cwd, { cwd, chats: [session] })
	}
	const unused = kept && empty ? [...kept].filter((cwd) => !workspaces.has(cwd)).reverse() : []
	return { folders: [...unused.map((cwd) => ({ cwd, chats: [] })), ...workspaces.values()], loose }
}

// every chat and workspace in its manual place, the ones not placed yet on top as "Last
// updated" lists them; `fresh` starts from that order instead
function manualOrders(fresh = false) {
	const { sessions, prefs } = flow.state
	const folders = byWorkspace(sessions).folders.map((folder) => folder.cwd)
	return {
		chatOrder: arrange(sessions.map((session) => session.session_id), fresh ? [] : prefs.chatOrder),
		folderOrder: arrange(folders, fresh ? [] : prefs.folderOrder),
	}
}

// in manual order a new chat or workspace takes the top, then keeps its place; only a
// full list can say which saved places are gone
watch(
	() => manual.value && !flow.state.sessionsMore && !flow.state.sessionQuery && flow.state.sessions,
	(sessions) => {
		if (!sessions?.length) return
		const orders = manualOrders()
		const same = (a, b = []) => a.length === b.length && a.every((key, i) => key === b[i])
		if (!same(orders.chatOrder, flow.state.prefs.chatOrder) || !same(orders.folderOrder, flow.state.prefs.folderOrder))
			flow.setSidebarView(orders)
	},
	{ immediate: true },
)

// a workspace per folder, most recent or in manual order, empty ones hidden while searching;
// chats in none come last, ungrouped, and in one list nothing groups
const groups = computed(() => {
	const chats = manual.value ? arrange(filtered.value, flow.state.prefs.chatOrder, (s) => s.session_id) : filtered.value
	if (!grouped.value) return [{ cwd: null, open: true, chats }]
	const { folders, loose } = byWorkspace(chats, !searching.value)
	const ordered = manual.value ? arrange(folders, flow.state.prefs.folderOrder, (folder) => folder.cwd) : folders
	const groups = ordered.map(({ cwd, chats }) => {
		const all = searching.value || showingAll.value.includes(cwd)
		const shown = all ? chats : chats.filter((s, i) => i < CHATS_SHOWN || s.session_id === flow.state.sessionId)
		const hidden = chats.length - shown.length
		const collapsible = !searching.value && all && chats.length > CHATS_SHOWN
		return {
			cwd,
			name: flow.folderName(cwd),
			open: searching.value || flow.state.prefs.openFolders.includes(cwd),
			chats: shown,
			toggle: hidden ? `Show ${hidden} more` : collapsible ? "Show less" : null,
		}
	})
	if (loose.length) groups.push({ cwd: null, open: true, chats: loose })
	return groups
})

function toggleWorkspace(cwd) {
	if (pressed) {
		pressed = false
		return
	}
	if (searching.value) return // a search holds every workspace with a match open
	flow.setFolderOpen(cwd, !flow.state.prefs.openFolders.includes(cwd))
}

function toggleShowAll(cwd) {
	const all = showingAll.value
	showingAll.value = all.includes(cwd) ? all.filter((path) => path !== cwd) : [...all, cwd]
}

// the chat on screen opens its workspace, each time another one comes on screen
watch(
	[
		() => flow.state.sessionId,
		() => {
			const { sessionId, sessions, session, prefs } = flow.state
			if (!sessionId) return prefs.cwd ?? null
			return sessions.find((s) => s.session_id === sessionId)?.workspace ?? session?.config?.cwd ?? null
		},
	],
	([, cwd]) => {
		if (cwd && !flow.state.prefs.openFolders.includes(cwd)) flow.setFolderOpen(cwd, true)
	},
	{ immediate: true },
)

// a row dragged with the mouse lands before or after the row it is let go over, among the
// rows of its own scope: the workspaces, or one workspace's chats. A drop in last-updated
// order switches to manual, starting from the order on screen
const dragging = ref(null) // { scope, key, over, after }
let endDrag = null // ends the drag in flight, dropping nothing
onBeforeUnmount(() => endDrag?.({ type: "pointercancel" }))
function dragStart(scope, key, event) {
	pressed = false
	// a Mac's ctrl-click is a right click, whose context menu swallows the release
	if (!canReorder.value || event.pointerType !== "mouse" || event.button !== 0 || event.ctrlKey) return
	const startY = event.clientY
	const move = (e) => {
		if (!(e.buttons & 1)) return end(e) // the release never came: nothing drops
		if (!dragging.value && Math.abs(e.clientY - startY) < 4) return
		cardFor.value = null
		const row = document.elementFromPoint(e.clientX, e.clientY)?.closest("[data-reorder]")
		const target = row?.dataset.reorder === scope && row.dataset.key !== key ? row : null
		const box = target?.getBoundingClientRect()
		dragging.value = { scope, key, over: target?.dataset.key, after: !!box && e.clientY > box.top + box.height / 2 }
	}
	const end = (e) => {
		endDrag = null
		window.removeEventListener("pointermove", move)
		window.removeEventListener("pointerup", end)
		window.removeEventListener("pointercancel", end)
		const drop = dragging.value
		dragging.value = null
		if (!drop) return
		// the click this release makes must not open or fold a row; no later one is it
		pressed = true
		setTimeout(() => (pressed = false))
		if (drop.over && e.type === "pointerup") reorder(drop)
	}
	endDrag = end
	window.addEventListener("pointermove", move)
	window.addEventListener("pointerup", end)
	window.addEventListener("pointercancel", end)
}

function reorder({ scope, key, over, after }) {
	const orders = manualOrders(!manual.value)
	const name = scope === "folder" ? "folderOrder" : "chatOrder"
	const order = orders[name].filter((k) => k !== key)
	order.splice(order.indexOf(over) + (after ? 1 : 0), 0, key)
	flow.setSidebarView({ ...orders, [name]: order, sidebarOrder: "manual" })
	// a chat dropped beside the open one, shown past its workspace's first chats, can land
	// among the hidden ones: the workspace then shows them all
	const cwd = scope.slice("chat:".length)
	const shown = groups.value.find((group) => group.cwd === cwd)?.chats.some((s) => s.session_id === key)
	if (scope !== "folder" && cwd && !shown) showingAll.value = [...showingAll.value, cwd]
}

// the dragged row dims, and a line shows where it would land
function dragClass(key) {
	const drop = dragging.value
	if (drop?.key === key) return "opacity-50"
	if (drop?.over === key) return drop.after ? "drop-after" : "drop-before"
	return null
}

// touch has no hover to reveal a row's buttons: a long press opens its menu (a chat's id, a
// workspace's folder) instead
let pressTimer = null
let pressed = false // the click that ends a long press or a drag must not open or fold a row
function pressStart(key, event) {
	clearTimeout(pressTimer)
	pressed = false
	if (event.pointerType !== "touch") return
	pressTimer = setTimeout(() => {
		pressed = true
		menuFor.value = key
	}, 500)
}
function pressEnd() {
	clearTimeout(pressTimer)
}
onBeforeUnmount(pressEnd)

// a drawer closes once a chat is picked, and the chat opens once the host lets it
async function pick(session) {
	if (pressed) {
		pressed = false
		return
	}
	if (layout.narrow) emit("close")
	if (props.beforeSwitch && !(await props.beforeSwitch())) return
	flow.openSession(session.session_id)
}

// with no folder, the new chat starts in the open chat's
async function startNewChat(cwd = null) {
	if (layout.narrow) emit("close")
	if (props.beforeSwitch && !(await props.beforeSwitch())) return
	flow.startNewChat({ cwd })
}

// a folder picked in the daemon's folder dialog: its workspace at once, and a new chat in it
async function newWorkspace() {
	const cwd = await flow.pickFolder()
	if (!cwd) return
	const workspace = await flow.addFolder(cwd)
	if (flow.state.folders && !workspace) return // refused, as the toast says
	startNewChat(workspace?.path ?? cwd)
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

const sliding = useSlide(() => props.open)

// a phone's drawer opens with a swipe in from the screen's left edge and closes with a swipe
// back, as its other chat apps' do; a dialog or the settings page keeps its own touches
let swipe = null
function swipeStart(event) {
	const { clientX: x, clientY: y } = event.touches[0]
	const free = layout.phone && event.touches.length === 1 && !event.target.closest?.("[role=dialog]")
	swipe = free && (props.open || x < 24) ? { x, y } : null
}
function swipeEnd(event) {
	if (!swipe) return
	const dx = event.changedTouches[0].clientX - swipe.x
	const dy = event.changedTouches[0].clientY - swipe.y
	swipe = null
	if (Math.abs(dx) < 60 || Math.abs(dx) < 2 * Math.abs(dy)) return
	if (dx > 0 && !props.open) flow.setSidebarOpen(true)
	else if (dx < 0 && props.open) emit("close")
}
onMounted(() => {
	window.addEventListener("touchstart", swipeStart, { passive: true })
	window.addEventListener("touchend", swipeEnd, { passive: true })
})
onBeforeUnmount(() => {
	window.removeEventListener("touchstart", swipeStart)
	window.removeEventListener("touchend", swipeEnd)
})

const filtered = computed(() => {
	const q = debouncedQuery.value.trim().toLowerCase()
	return flow.state.sessions.filter((session) => !q || flow.sessionTitle(session).toLowerCase().includes(q))
})

const emptyMessage = computed(() => {
	if (query.value) return "No matches."
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

/* a card's top lines up with its row's title, which left the card's own title a padding
   lower: lift the card by that padding, so the two titles sit on one line */
:global([data-reka-popper-content-wrapper]:has(.row-card)) {
	translate: 0 -0.625rem;
}

/* a phone's drawer: rows and buttons a finger can take, titles a half step over the chat's text */
@media (max-width: 767px) and (pointer: coarse) {
	aside :deep([data-slot="sidebar-item"]),
	.list-head {
		height: 2.75rem;
	}
	.list-head button {
		width: 2.25rem;
		height: 2.25rem;
	}
	.row-title,
	aside :deep([data-slot="sidebar-item"]) .text-xs {
		font-size: 15.5px;
	}
}

/* in one list, chats rest half a step quieter, so the long column reads calmer; the one
   under the pointer and the open one keep full ink */
.quiet[data-state="inactive"]:not(:hover, .menu-open) {
	color: color-mix(in srgb, var(--ink-gray-7) 50%, var(--ink-gray-8));
}

/* chat and workspace names a half step over text-xs in size and weight, keeping its spacing; a
   long one fades out at the row's end */
.row-title {
	font-size: 13.5px;
	font-weight: 460;
	-webkit-mask-image: linear-gradient(to right, #000 calc(100% - 1.5rem), transparent);
	mask-image: linear-gradient(to right, #000 calc(100% - 1.5rem), transparent);
}

/* a row's button covers the end of its title, so a long title fades out before it; touch
   screens show a workspace's button without a hover */
.group:hover .row-title,
[data-flow-tabbing] .group:has(:focus-visible) .row-title,
.group.menu-open .row-title {
	-webkit-mask-image: linear-gradient(to right, #000 calc(100% - 3rem), transparent calc(100% - 1.5rem));
	mask-image: linear-gradient(to right, #000 calc(100% - 3rem), transparent calc(100% - 1.5rem));
}
/* a workspace's row has two buttons, its menu's and a new chat's */
.workspace-menu:hover .row-title,
[data-flow-tabbing] .workspace-menu:has(:focus-visible) .row-title,
.workspace-menu.menu-open .row-title {
	-webkit-mask-image: linear-gradient(to right, #000 calc(100% - 5rem), transparent calc(100% - 3.5rem));
	mask-image: linear-gradient(to right, #000 calc(100% - 5rem), transparent calc(100% - 3.5rem));
}
/* Tab onto a chat shows its options button, as a hover does (focusRings.js marks the root) */
[data-flow-tabbing] .group:has(:focus-visible) .chat-options {
	opacity: 1;
}
@media (hover: none) {
	.folder-name {
		-webkit-mask-image: linear-gradient(to right, #000 calc(100% - 3rem), transparent calc(100% - 1.5rem));
		mask-image: linear-gradient(to right, #000 calc(100% - 3rem), transparent calc(100% - 1.5rem));
	}
	.workspace-menu .folder-name {
		-webkit-mask-image: linear-gradient(to right, #000 calc(100% - 5rem), transparent calc(100% - 3.5rem));
		mask-image: linear-gradient(to right, #000 calc(100% - 5rem), transparent calc(100% - 3.5rem));
	}
}

/* a crawling title also fades in from its start */
.row-title[data-crawl] {
	-webkit-mask-image: linear-gradient(to right, transparent, #000 0.75rem, #000 calc(100% - 3rem), transparent calc(100% - 1.5rem));
	mask-image: linear-gradient(to right, transparent, #000 0.75rem, #000 calc(100% - 3rem), transparent calc(100% - 1.5rem));
}
.row-title[data-crawl] > span {
	transform: translateX(var(--crawl));
	transition: transform var(--crawl-time) linear;
}

/* a workspace's chats fold away and back; the column keeps a long title from widening the row */
.flow-fold {
	display: grid;
	grid-template-rows: 1fr;
	grid-template-columns: minmax(0, 1fr);
}
.flow-fold-enter-active,
.flow-fold-leave-active {
	transition:
		grid-template-rows 0.2s ease,
		opacity 0.2s ease;
}
.flow-fold-enter-active > div,
.flow-fold-leave-active > div {
	overflow: hidden;
}
.flow-fold-enter-from,
.flow-fold-leave-to {
	grid-template-rows: 0fr;
	opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
	.row-title[data-crawl] > span,
	.flow-fold-enter-active,
	.flow-fold-leave-active {
		transition: none;
	}
}

/* where a dragged row would land: a line in the gap above or below the row */
.drop-before::before,
.drop-after::after {
	content: "";
	position: absolute;
	left: 0.5rem;
	right: 0.5rem;
	height: 2px;
	border-radius: 1px;
	background: var(--ink-gray-3);
}
.drop-before::before {
	top: -2px;
}
.drop-after::after {
	bottom: -2px;
}
/* one list's 6px gaps, all but a phone's: the line keeps to their middle */
@media not all and (max-width: 767px) and (pointer: coarse) {
	.quiet.drop-before::before {
		top: -4px;
	}
	.quiet.drop-after::after {
		bottom: -4px;
	}
}
.flow-reordering :deep(*) {
	cursor: grabbing !important;
}
.flow-reordering .row-action {
	visibility: hidden;
}
</style>
