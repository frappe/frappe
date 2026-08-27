<template>
	<Transition name="flow-backdrop">
		<button
			v-if="workspace.open && !workspace.maximized"
			class="fixed inset-0 z-20 bg-black/30 md:hidden"
			aria-label="Close panel"
			@click="flow.setWorkspaceOpen(false)"
		/>
	</Transition>
	<aside
		class="flex flex-col border-l border-outline-gray-1 bg-surface-base"
		:class="[
			workspace.maximized
				? 'fixed inset-0 z-40'
				: 'fixed inset-y-0 right-0 z-30 w-[var(--workspace-w)] max-w-full flex-none md:relative',
			ready ? 'transition-[transform,margin-right] duration-200 ease-in-out' : '',
			// mirror of the left sidebar: no transform while open (a transformed
			// aside would clip monaco's fixed overflow widgets and dialogs)
			workspace.open || workspace.maximized
				? ''
				: 'translate-x-full md:mr-[calc(-1*var(--workspace-w))] md:translate-x-0',
		]"
		:style="workspace.maximized ? {} : { '--workspace-w': width + 'px' }"
	>
		<div
			v-if="!workspace.maximized"
			class="absolute inset-y-0 left-0 z-10 hidden w-1 cursor-col-resize hover:bg-[--outline-gray-2] active:bg-[--outline-gray-3] md:block"
			title="Drag to resize · double-click to reset"
			@pointerdown="startResize"
			@dblclick="resetWidth"
		/>

		<!-- panel-level tab strip: one tab per open item of any kind (editor today,
		     browser/terminal later) — kind-specific chrome lives in the view below.
		     The view picker (nothing open) renders without it. -->
		<div
			v-if="viewActive"
			class="flex h-11 flex-none items-stretch border-b border-outline-gray-1 bg-surface-base"
		>
			<div class="flow-tab-strip flex min-w-0 items-center gap-1 overflow-x-auto px-1.5" role="tablist">
				<div
					v-for="tab in workspace.tabs"
					:key="tab.path"
					role="tab"
					tabindex="0"
					:aria-selected="tab.path === workspace.active"
					class="flow-tab group flex h-7 min-w-[96px] shrink basis-40 cursor-pointer items-center gap-1.5 rounded-5 pl-2.5 pr-1 text-xs"
					:class="
						tab.path === workspace.active
							? 'flow-tab-active bg-surface-gray-2 text-ink-gray-9'
							: 'text-ink-gray-5 hover:bg-surface-gray-1 hover:text-ink-gray-8'
					"
					:title="tab.path"
					@click="flow.selectFile(tab.path)"
					@keydown.enter.prevent="flow.selectFile(tab.path)"
				>
					<span class="flow-tab-label min-w-0 flex-1 text-left">{{ tab.name }}</span>
					<button
						class="grid h-4 w-4 flex-none place-items-center rounded-4 text-ink-gray-4 hover:bg-surface-gray-3 hover:text-ink-gray-8"
						:class="tab.path === workspace.active || tab.dirty ? '' : 'opacity-0 group-hover:opacity-100'"
						:title="tab.dirty ? 'Unsaved changes — close file' : 'Close file'"
						@click.stop="requestClose(tab)"
					>
						<span v-if="tab.dirty" class="flow-dirty-dot h-2 w-2 rounded-full bg-ink-gray-6" />
						<FeatherIcon name="x" class="h-3 w-3" :class="tab.dirty ? 'flow-dirty-x hidden' : ''" />
					</button>
				</div>
				<!-- transient view tab: stands in until a file is picked, which replaces it -->
				<div
					v-if="transientTab"
					role="tab"
					aria-selected="true"
					class="flow-tab flow-tab-active flex h-7 min-w-[96px] shrink basis-40 cursor-default items-center gap-1.5 rounded-5 bg-surface-gray-2 pl-2.5 pr-1 text-xs text-ink-gray-9"
				>
					<span class="flow-tab-label min-w-0 flex-1 text-left">{{ transientTab }}</span>
					<button
						class="grid h-4 w-4 flex-none place-items-center rounded-4 text-ink-gray-4 hover:bg-surface-gray-3 hover:text-ink-gray-8"
						title="Close"
						@click="flow.closeFilesView()"
					>
						<FeatherIcon name="x" class="h-3 w-3" />
					</button>
				</div>
				<Dropdown class="flex-none" :options="addTabOptions">
					<template #trigger>
						<button class="flow-icon-btn" title="New tab">
							<FeatherIcon name="plus" class="h-3.5 w-3.5" />
						</button>
					</template>
				</Dropdown>
			</div>
			<span class="flex-1" />
			<button
				class="flow-icon-btn my-1 flex-none self-center"
				:title="workspace.maximized ? 'Exit full screen' : 'Full screen'"
				@click="flow.toggleWorkspaceMaximized()"
			>
				<FeatherIcon :name="workspace.maximized ? 'minimize-2' : 'maximize-2'" class="h-3.5 w-3.5" />
			</button>
			<button
				class="flow-icon-btn my-1 mr-1 flex-none self-center"
				title="Close panel"
				@click="flow.setWorkspaceOpen(false)"
			>
				<FeatherIcon name="sidebar" class="h-3.5 w-3.5 -scale-x-100" />
			</button>
		</div>

		<!-- kind-specific body; only the editor kind exists so far -->
		<EditorView v-if="viewActive" />

		<!-- nothing open and no view picked: the view picker (no tab strip, but the
		     panel's window controls stay reachable) -->
		<div v-else class="relative flex flex-1 flex-col items-center justify-center gap-3 px-6">
			<span class="absolute right-1 top-1 flex">
				<button
					class="flow-icon-btn"
					:title="workspace.maximized ? 'Exit full screen' : 'Full screen'"
					@click="flow.toggleWorkspaceMaximized()"
				>
					<FeatherIcon :name="workspace.maximized ? 'minimize-2' : 'maximize-2'" class="h-3.5 w-3.5" />
				</button>
				<button class="flow-icon-btn" title="Close panel" @click="flow.setWorkspaceOpen(false)">
					<FeatherIcon name="sidebar" class="h-3.5 w-3.5 -scale-x-100" />
				</button>
			</span>
			<button
				class="flex w-44 items-center gap-2.5 rounded-6 border border-outline-gray-2 px-3 py-2.5 text-sm text-ink-gray-8 transition-colors hover:bg-surface-gray-1"
				@click="flow.showFilesView()"
			>
				<FeatherIcon name="folder" class="h-4 w-4 flex-none text-ink-gray-5" />
				Files
			</button>
			<button
				class="flex w-44 items-center gap-2.5 rounded-6 border border-outline-gray-2 px-3 py-2.5 text-sm text-ink-gray-8 transition-colors hover:bg-surface-gray-1"
				@click="flow.showDiffView()"
			>
				<FeatherIcon name="columns" class="h-4 w-4 flex-none text-ink-gray-5" />
				Diffs
			</button>
		</div>
	</aside>
</template>

<script setup>
import { computed, inject, onMounted, ref } from "vue"
import Dropdown from "frappe-ui/src/components/Dropdown/Dropdown.vue"
import FeatherIcon from "./FeatherIcon.vue"
import { dialog } from "frappe-ui/src/utils/dialog"

import EditorView from "./EditorView.vue"

const flow = inject("flow")
const workspace = computed(() => flow.state.workspace)
const activeTab = computed(
	() => workspace.value.tabs.find((tab) => tab.path === workspace.value.active) ?? null,
)
// a view (editor, files, or diffs) is showing; false means the view picker
const viewActive = computed(
	() => activeTab.value?.kind === "editor" || ["files", "diff"].includes(workspace.value.view),
)
// label of the stand-in tab shown while the view has no file open yet
const transientTab = computed(() =>
	activeTab.value ? null : ({ files: "Files", diff: "Diffs" }[workspace.value.view] ?? null),
)

// the panel stays mounted while closed so it can slide like the left sidebar
const ready = ref(false)
onMounted(() => requestAnimationFrame(() => (ready.value = true)))

// "+" menu: one entry per tab kind the panel can host (browser, terminal later)
const addTabOptions = [
	{ label: "Files", icon: "lucide-folder", onClick: () => flow.showFilesView() },
	{ label: "Diffs", icon: "lucide-file-diff", onClick: () => flow.showDiffView() },
]

function requestClose(tab) {
	if (!tab.dirty) return flow.closeFile(tab.path)
	dialog.confirm({
		title: "Discard changes?",
		message: `“${tab.name}” has unsaved changes.`,
		actions: [
			{ label: "Cancel", variant: "outline" },
			{ label: "Discard", variant: "solid", theme: "red", onClick: () => flow.closeFile(tab.path) },
		],
	})
}

const DEFAULT_WIDTH = 460
const clampWidth = (w) => Math.min(720, Math.max(320, w))
const width = ref(clampWidth(flow.state.prefs.workspaceWidth ?? DEFAULT_WIDTH))

function resetWidth() {
	width.value = DEFAULT_WIDTH
	flow.setWorkspaceWidth(DEFAULT_WIDTH)
}

function startResize(event) {
	event.preventDefault()
	const handle = event.currentTarget
	handle.setPointerCapture(event.pointerId)
	const startX = event.clientX
	const startWidth = width.value
	const move = (e) => (width.value = clampWidth(startWidth - (e.clientX - startX)))
	const up = (e) => {
		handle.releasePointerCapture(e.pointerId)
		handle.removeEventListener("pointermove", move)
		handle.removeEventListener("pointerup", up)
		handle.removeEventListener("pointercancel", up)
		flow.setWorkspaceWidth(width.value)
	}
	handle.addEventListener("pointermove", move)
	handle.addEventListener("pointerup", up)
	handle.addEventListener("pointercancel", up)
}
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

.flow-tab-strip {
	scrollbar-width: thin;
}

/* codex-style divider centered in the 4px gap between adjacent tabs */
.flow-tab {
	position: relative;
}
.flow-tab + .flow-tab::before {
	content: "";
	position: absolute;
	left: -2.5px;
	top: 50%;
	height: 12px;
	width: 1px;
	transform: translateY(-50%);
	background: var(--outline-gray-2);
}
/* the active tab's own surface marks it; no dividers touching it */
.flow-tab-active::before,
.flow-tab-active + .flow-tab::before {
	display: none;
}

/* long tab names fade out at the right edge instead of clipping to an ellipsis */
.flow-tab-label {
	overflow: hidden;
	white-space: nowrap;
	-webkit-mask-image: linear-gradient(90deg, #000 calc(100% - 14px), transparent);
	mask-image: linear-gradient(90deg, #000 calc(100% - 14px), transparent);
}

/* VSCode-style dirty marker: the dot swaps to an × when hovering the close button */
button:hover > .flow-dirty-dot {
	display: none;
}
button:hover > .flow-dirty-x {
	display: block;
}
</style>
