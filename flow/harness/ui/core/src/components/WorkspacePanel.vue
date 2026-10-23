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
			sliding ? 'transition-[transform,margin-right] duration-200 ease-in-out' : '',
			// mirror of the left sidebar: no transform while open (a transformed
			// aside would clip monaco's fixed overflow widgets and dialogs)
			workspace.open || workspace.maximized
				? ''
				: 'translate-x-full md:mr-[calc(-1*var(--workspace-w))] md:translate-x-0',
		]"
		:style="workspace.maximized ? {} : { '--workspace-w': width + 'px' }"
		:inert="!workspace.open && !workspace.maximized"
	>
		<div
			v-if="!workspace.maximized"
			class="absolute inset-y-0 left-0 z-10 hidden w-1 cursor-col-resize hover:bg-[--outline-gray-2] active:bg-[--outline-gray-3] md:block"
			title="Drag to resize · double-click to reset"
			@pointerdown="startResize"
			@dblclick="resetWidth"
		/>

		<!-- panel-level tab strip: one tab per open item of any kind (a file, a sub-agent;
		     browser/terminal later) — kind-specific chrome lives in the view below.
		     The view picker (nothing open) renders without it. -->
		<div
			v-if="viewActive"
			class="flex h-11 flex-none items-stretch border-b border-outline-gray-1 bg-surface-base"
		>
			<!-- flex-1 makes the strip's width definite (the whole row minus the window
			     controls), so tabs hold their basis cap and shrink together only once
			     they stop fitting — a shrink-to-fit strip would hug the labels instead -->
			<div class="flow-tab-strip flex min-w-0 flex-1 items-center gap-1 overflow-x-auto px-1.5" role="tablist">
				<div
					v-for="tab in workspace.tabs"
					:key="tab.path"
					role="tab"
					tabindex="0"
					:aria-selected="tab.path === workspace.active"
					class="flow-tab group flex h-7 min-w-12 shrink basis-60 cursor-pointer items-center gap-1.5 rounded-5 pl-2.5 pr-1 text-xs"
					:class="
						tab.path === workspace.active
							? 'flow-tab-active bg-surface-gray-2 text-ink-gray-9'
							: 'text-ink-gray-5 hover:bg-surface-gray-1 hover:text-ink-gray-8'
					"
					:title="tab.kind === 'editor' ? tab.path : tab.name"
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
					class="flow-tab flow-tab-active flex h-7 min-w-12 shrink basis-60 cursor-default items-center gap-1.5 rounded-5 bg-surface-gray-2 pl-2.5 pr-1 text-xs text-ink-gray-9"
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
				<!-- the host's additions to the strip: its "+" menu of the views it serves -->
				<slot name="actions" />
			</div>
			<!-- a narrow frame's panel already fills it -->
			<button
				v-if="!layout.narrow"
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

		<!-- kind-specific body: a sub-agent's thread, or the host's view of any other tab -->
		<SubagentView v-if="activeTab?.kind === 'subagent'" :id="activeTab.path" />
		<!-- kept mounted, hidden, while it has tabs: it holds their unsaved edits -->
		<div v-if="showView || keepView" v-show="showView" class="flex min-h-0 flex-1 flex-col">
			<slot name="view" :tab="activeTab" />
		</div>

		<!-- nothing open and no view picked: the host's empty state (no tab strip, but the
		     panel's window controls stay reachable) -->
		<div v-if="!viewActive" class="relative flex flex-1 flex-col items-center justify-center gap-3 px-6">
			<span class="absolute right-1 top-1 flex">
				<button
					v-if="!layout.narrow"
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
			<slot name="empty" />
		</div>
	</aside>
</template>

<script setup>
import { computed, inject, ref } from "vue"
import FeatherIcon from "./FeatherIcon.vue"
import { dialog } from "frappe-ui/src/utils/dialog"

import SubagentView from "./SubagentView.vue"
import { layout, useSlide } from "../layout.js"

const flow = inject("flow")
const workspace = computed(() => flow.state.workspace)
const activeTab = computed(
	() => workspace.value.tabs.find((tab) => tab.path === workspace.value.active) ?? null,
)
// a view (a tab, files, or diffs) is showing; false means the view picker
const viewActive = computed(() => !!activeTab.value || ["files", "diff"].includes(workspace.value.view))
// the host's view is on screen: not a sub-agent's thread, not the picker
const showView = computed(() => viewActive.value && activeTab.value?.kind !== "subagent")
const keepView = computed(() => workspace.value.tabs.some((tab) => tab.kind !== "subagent"))
// label of the stand-in tab shown while the view has no file open yet
const transientTab = computed(() =>
	activeTab.value ? null : ({ files: "Files", diff: "Diffs" }[workspace.value.view] ?? null),
)

// the panel stays mounted while closed so it can slide like the left sidebar
const sliding = useSlide(() => workspace.value.open || workspace.value.maximized)

function requestClose(tab) {
	if (!tab.dirty) return flow.closeFile(tab.path)
	dialog.confirm({
		title: "Discard changes?",
		size: "lg",
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
