<template>
	<div class="pointer-events-none absolute inset-x-0 bottom-0 z-10 px-5 pb-3.5">
		<div class="pointer-events-auto relative mx-auto max-w-[800px]">
			<ModelPalette
				v-if="paletteView === 'models'"
				@close="closePalettes"
				@back="paletteView = 'commands'"
				@providers="paletteView = 'providers'"
			/>
			<ThinkingPalette
				v-if="paletteView === 'thinking'"
				@close="closePalettes"
				@back="paletteView = 'commands'"
			/>
			<ProvidersDialog
				v-if="paletteView === 'providers'"
				@close="closePalettes"
				@back="paletteView = 'commands'"
			/>

			<!-- slash-command palette -->
			<PalettePanel v-if="menuOpen" title="Commands" @close="closePalettes">
				<div ref="menuListEl" class="overflow-y-auto p-1.5">
					<button
						v-for="(m, i) in menuItems"
						:key="m.name"
						:data-palette-active="i === menuIdx"
						class="flex w-full items-center gap-3 rounded-md px-2.5 py-2 text-left hover:bg-surface-gray-2"
						:class="{ 'bg-surface-gray-2': i === menuIdx }"
						@mouseenter="menuIdx = i"
						@click="pick(m)"
					>
						<span
							class="flex h-7 w-7 flex-none items-center justify-center rounded-md border border-outline-gray-1 bg-surface-gray-1 text-ink-gray-6"
						>
							<FeatherIcon :name="m.icon" class="h-3.5 w-3.5" />
						</span>
						<span class="min-w-0 flex-1">
							<span class="block text-xs font-medium leading-4 text-ink-gray-9">{{ m.label }}</span>
							<span class="mt-1 block truncate text-2xs leading-4 text-ink-gray-5">{{ m.hint }}</span>
						</span>
						<code class="text-2xs text-ink-gray-4">/{{ m.name }}</code>
					</button>
					<div v-if="!menuItems.length" class="px-3 py-8 text-center text-xs text-ink-gray-5">
						No matching commands
					</div>
				</div>
			</PalettePanel>

			<!-- queued steering -->
			<div
				v-if="flow.state.queued.length"
				class="-mb-1 flex items-baseline gap-2 rounded-t-[10px] border border-b-0 border-outline-gray-2 bg-surface-gray-2 px-3 pb-3 pt-2"
			>
				<span class="flex-none text-2xs font-medium text-ink-gray-6">Queued</span>
				<span class="min-w-0 flex-1 truncate text-xs text-ink-gray-7">{{
					flow.state.queued.join(" · ")
				}}</span>
			</div>

			<div
				class="flex flex-col gap-2 rounded-xl border border-outline-gray-2 bg-surface-white p-2 shadow-[0_1px_3px_rgba(0,0,0,0.035)]"
			>
				<textarea
					ref="box"
					v-model="text"
					:rows="rows"
					placeholder="Ask flow…"
					class="max-h-40 min-h-[62px] w-full resize-none border-0 bg-transparent px-1.5 pt-1 text-base leading-relaxed text-ink-gray-9 outline-none placeholder:text-ink-gray-4 focus:ring-0"
					@keydown="onKey"
				/>
				<div class="flex min-w-0 items-center gap-1">
					<!-- add-context menu: project folder now, file uploads later -->
					<span class="relative flex-none">
						<button
							class="grid h-7 w-7 place-items-center rounded-md text-ink-gray-6 hover:bg-surface-gray-2 hover:text-ink-gray-9"
							:class="plusMenu ? 'bg-surface-gray-2' : ''"
							title="Add context"
							@click="plusMenu = !plusMenu"
						>
							<FeatherIcon name="plus" class="h-4 w-4" />
						</button>
						<PopMenu :open="plusMenu" :width="266" @close="plusMenu = false">
							<button class="flex w-full items-start gap-2.5 rounded-[10px] px-2.5 py-2 text-left hover:bg-surface-gray-2" @click="chooseFolder">
								<FeatherIcon name="folder" class="mt-0.5 h-3.5 w-3.5 flex-none text-ink-gray-5" />
								<span class="min-w-0 flex-1">
									<span class="block text-xs font-medium leading-4 text-ink-gray-9">Project folder</span>
									<span class="mt-1 block truncate text-2xs leading-4 text-ink-gray-5" :title="flow.state.prefs.cwd ?? ''">
										{{ cwdLabel }}
									</span>
								</span>
							</button>
							<div class="flex w-full cursor-not-allowed items-start gap-2.5 rounded-[10px] px-2.5 py-2 text-left opacity-50">
								<FeatherIcon name="paperclip" class="mt-0.5 h-3.5 w-3.5 flex-none text-ink-gray-5" />
								<span class="min-w-0 flex-1">
									<span class="block text-xs font-medium leading-4 text-ink-gray-9">Attach files</span>
									<span class="mt-1 block text-2xs leading-4 text-ink-gray-5">Coming soon</span>
								</span>
							</div>
						</PopMenu>
					</span>

					<!-- model picker: a menu of the two palettes it fronts -->
					<span class="relative min-w-0">
						<button
							class="flex h-7 min-w-0 max-w-[230px] items-center gap-1.5 rounded-md px-2 text-xs font-medium text-ink-gray-7 hover:bg-surface-gray-2"
							:class="modelMenu ? 'bg-surface-gray-2' : ''"
							:title="`${modelLabel} · thinking ${effortLabel}`"
							@click="modelMenu = !modelMenu"
						>
							<FeatherIcon name="cpu" class="h-3.5 w-3.5 flex-none text-ink-gray-5" />
							<span class="min-w-0 truncate">{{ modelLabel }}</span>
							<template v-if="currentEffort !== 'default'">
								<span class="h-[3px] w-[3px] flex-none self-center rounded-full bg-surface-gray-4" />
								<span class="flex-none font-normal text-ink-gray-5">{{ effortLabel }}</span>
							</template>
							<FeatherIcon name="chevron-down" class="h-3 w-3 flex-none text-ink-gray-4" />
						</button>
						<PopMenu :open="modelMenu" :width="266" @close="modelMenu = false">
							<button
								v-for="entry in MODEL_MENU"
								:key="entry.view"
								class="flex w-full items-start gap-2.5 rounded-[10px] px-2.5 py-2 text-left hover:bg-surface-gray-2"
								@click="openPalette(entry.view)"
							>
								<FeatherIcon
									:name="entry.icon"
									class="mt-0.5 h-3.5 w-3.5 flex-none text-ink-gray-5"
								/>
								<span class="min-w-0 flex-1">
									<span class="block text-xs font-medium leading-4 text-ink-gray-9">
										{{ entry.label }}
									</span>
									<span class="mt-1 block truncate text-2xs leading-4 text-ink-gray-5">
										{{ entry.value }}
									</span>
								</span>
								<FeatherIcon
									name="chevron-right"
									class="h-3.5 w-3.5 flex-none self-center text-ink-gray-4"
								/>
							</button>
						</PopMenu>
					</span>

					<span class="min-w-2 flex-1" />

					<!-- approval mode -->
					<span class="relative flex-none">
						<button
							class="flex h-7 items-center gap-1.5 whitespace-nowrap rounded-md px-2 text-xs font-medium text-ink-gray-7 hover:bg-surface-gray-2"
							:class="modeMenu ? 'bg-surface-gray-2' : ''"
							title="Approval mode"
							@click="modeMenu = !modeMenu"
						>
							{{ currentMode === "auto" ? "Auto-approve" : "Ask for approval" }}
							<FeatherIcon name="chevron-down" class="h-3 w-3 flex-none text-ink-gray-4" />
						</button>
						<PopMenu :open="modeMenu" align="right" :width="266" @close="modeMenu = false">
							<button
								v-for="m in MODES"
								:key="m.id"
								class="flex w-full items-start gap-2 rounded-[10px] px-2.5 py-2 text-left hover:bg-surface-gray-2"
								:class="currentMode === m.id ? 'bg-surface-gray-2' : ''"
								@click="chooseMode(m.id)"
							>
								<span class="min-w-0 flex-1">
									<span class="block text-xs font-medium text-ink-gray-9">{{ m.label }}</span>
									<span class="mt-0.5 block text-2xs leading-snug text-ink-gray-5">{{ m.desc }}</span>
								</span>
								<FeatherIcon
									v-if="currentMode === m.id"
									name="check"
									class="mt-0.5 h-3 w-3 flex-none text-ink-gray-7"
								/>
							</button>
						</PopMenu>
					</span>

					<button
						v-if="running"
						class="ml-1 grid h-8 w-8 flex-none place-items-center rounded-lg border border-outline-gray-2 bg-surface-white text-ink-gray-7 hover:bg-surface-gray-2 hover:text-ink-gray-9"
						title="Stop"
						@click="flow.abort()"
					>
						<span class="h-2.5 w-2.5 rounded-sm bg-current" />
					</button>
					<button
						v-else
						class="ml-1 grid h-8 w-8 flex-none place-items-center rounded-lg shadow-sm"
						:class="
							canSend
								? 'bg-surface-gray-7 text-ink-white hover:opacity-90'
								: 'pointer-events-none bg-surface-gray-3 text-ink-gray-4'
						"
						title="Send"
						@click="submit"
					>
						<FeatherIcon name="arrow-up" class="h-4 w-4" />
					</button>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue"
import FeatherIcon from "frappe-ui/src/components/FeatherIcon.vue"
import { dialogs as frappeDialogs } from "frappe-ui/src/utils/dialog"

import { usePaletteNav } from "../paletteNav.js"

import { EFFORT_LABELS } from "../transcript.js"
import ModelPalette from "./ModelPalette.vue"
import PalettePanel from "./PalettePanel.vue"
import PopMenu from "./PopMenu.vue"
import ProvidersDialog from "./ProvidersDialog.vue"
import ThinkingPalette from "./ThinkingPalette.vue"

const flow = inject("flow")

const text = ref("")
const box = ref(null)
// the palette is one stacked surface: commands is the root page, models,
// thinking and providers are sub-pages whose back arrow returns to it
const paletteView = ref(null) // null | "commands" | "models" | "thinking" | "providers"

function closePalettes() {
	paletteView.value = null
	if (text.value.startsWith("/")) text.value = ""
}

// typing a normal message dismisses a commands page left open by back-navigation
watch(text, (value) => {
	if (paletteView.value === "commands" && value && !value.startsWith("/")) paletteView.value = null
})

// hands land on the keyboard, not the mouse: focus on load and whenever the
// conversation changes (open, switch, new chat)
onMounted(() => {
	box.value?.focus()
	window.addEventListener("keydown", onWindowKey)
})
onBeforeUnmount(() => window.removeEventListener("keydown", onWindowKey))
watch(
	() => flow.state.sessionId,
	() => nextTick(() => box.value?.focus()),
)

const modeMenu = ref(false)
const plusMenu = ref(false)
const modelMenu = ref(false)

function openPalette(view) {
	modelMenu.value = false
	paletteView.value = view
}

const cwdLabel = computed(() => {
	const cwd = flow.state.prefs.cwd
	return cwd ? (cwd.split("/").filter(Boolean).pop() ?? cwd) : "Pick where new chats run"
})

async function chooseFolder() {
	plusMenu.value = false
	const path = await flow.pickFolder()
	if (!path) return
	flow.setCwd(path)
	// a running session's cwd is frozen; the new folder applies from the next chat
	if (flow.state.sessionId) flow.startNewChat()
}

const MODES = [
	{ id: "ask", label: "Ask for approval", desc: "Pauses before writes, edits and commands." },
	{ id: "auto", label: "Auto-approve", desc: "Runs every tool without stopping to ask." },
]

const COMMANDS = [
	{ name: "model", label: "Model", icon: "cpu", hint: "choose the model", stacked: true, run: () => (paletteView.value = "models") },
	{ name: "thinking", label: "Thinking", icon: "zap", hint: "set the reasoning effort", stacked: true, run: () => (paletteView.value = "thinking") },
	{ name: "providers", label: "Providers", icon: "key", hint: "connect model providers", stacked: true, run: () => (paletteView.value = "providers") },
	{ name: "new", label: "New chat", icon: "plus", hint: "start a fresh conversation", run: () => flow.startNewChat() },
	{ name: "rewind", label: "Rewind", icon: "rotate-ccw", hint: "branch from before your last message", run: rewind },
	{ name: "compact", label: "Compact", icon: "minimize-2", hint: "summarize and shrink context", run: () => flow.compact() },
	{ name: "abort", label: "Abort", icon: "square", hint: "interrupt the running turn", run: () => flow.abort() },
	{ name: "cwd", label: "Working directory", icon: "folder", hint: "new session in a folder: /cwd [path]", run: cwdCommand, takesArg: true },
]

const running = computed(() => flow.state.conversation.running)
const canSend = computed(() => text.value.trim().length > 0)

// inside a session the button reflects that session's live mode; outside, the
// preference new chats will be created with
const currentMode = computed(() => {
	if (!flow.state.sessionId) return flow.state.prefs.mode
	return flow.state.session?.config?.auto_approve ? "auto" : "ask"
})
const rows = computed(() => Math.min(6, Math.max(1, text.value.split("\n").length)))

const currentModel = computed(() => flow.state.conversation.model ?? flow.state.prefs.lastModel)
const currentEffort = computed(
	() => flow.state.conversation.reasoningEffort ?? flow.state.prefs.lastEffort ?? "default",
)
// button shows the bare model id; the provider prefix lives in the tooltip
const modelLabel = computed(() => {
	const model = currentModel.value
	if (!model) return "choose model"
	return model.split("/").slice(1).join("/") || model
})
const effortLabel = computed(() => EFFORT_LABELS[currentEffort.value] ?? "Default")

// the model button fronts these two palettes; /model and /thinking open the same pages
const MODEL_MENU = computed(() => [
	{ view: "models", label: "Model", icon: "cpu", value: modelLabel.value },
	{ view: "thinking", label: "Thinking", icon: "zap", value: effortLabel.value },
])

// slash palette: active while the draft starts with "/" and has no space yet,
// or when a sub-page navigated back to the commands root. A trailing space
// ("/cwd ") means the user is past command selection — the menu closes so
// Enter submits the command instead of re-picking it forever.
const slash = computed(() => {
	if (!text.value.startsWith("/")) return null
	const head = text.value.split("\n")[0]
	const [cmd, ...restParts] = head.slice(1).split(" ")
	return { query: cmd, arg: restParts.join(" "), picking: !head.includes(" ") }
})
const menuOpen = computed(
	() => (!!slash.value && slash.value.picking) || paletteView.value === "commands",
)
const menuItems = computed(() => {
	if (!menuOpen.value) return []
	const q = (slash.value?.query ?? "").toLowerCase()
	return COMMANDS.filter((c) => c.name.startsWith(q))
})

function onKey(e) {
	if (menuItems.value.length) {
		if (e.key === "ArrowDown") {
			e.preventDefault()
			moveMenu(1)
			return
		}
		if (e.key === "ArrowUp") {
			e.preventDefault()
			moveMenu(-1)
			return
		}
		if (e.key === "Enter" || e.key === "Tab") {
			e.preventDefault()
			pick(menuItems.value[menuIdx.value] ?? menuItems.value[0])
			return
		}
	}
	if (e.key === "Enter" && !e.shiftKey) {
		e.preventDefault()
		submit()
	}
	if (e.key === "Escape") {
		// close whatever is open first; a bare Escape stops the running turn.
		// stopPropagation keeps the panels' own window listeners (and the global
		// abort fallback below) from double-handling the same keypress.
		e.stopPropagation()
		if (anyMenuOpen()) {
			closePalettes()
			modeMenu.value = false
			plusMenu.value = false
			modelMenu.value = false
		} else if (running.value && !e.repeat) {
			flow.abort()
		}
	}
}

// frappe-ui dialogs (delete confirm, …) own Escape while any is open
function anyMenuOpen() {
	return !!(
		paletteView.value ||
		menuOpen.value ||
		modeMenu.value ||
		plusMenu.value ||
		modelMenu.value ||
		frappeDialogs.value.length
	)
}

// Escape aborts even when focus is outside the textarea (reading, after a
// click). Open panels close themselves via their own Escape listeners.
// e.repeat: a held key must not spam abort requests.
function onWindowKey(e) {
	if (e.key !== "Escape" || e.repeat || anyMenuOpen()) return
	if (running.value) flow.abort()
}

function pick(command) {
	menuIdx.value = 0
	if (command.takesArg) {
		paletteView.value = null
		text.value = `/${command.name} `
		box.value?.focus()
		return
	}
	if (text.value.startsWith("/")) text.value = ""
	// stacked commands swap to their sub-page (run assigns it); the rest close
	if (!command.stacked) paletteView.value = null
	command.run()
}

// same arrow/Enter behaviour as the model and provider palettes
const {
	activeIndex: menuIdx,
	listEl: menuListEl,
	move: moveMenu,
} = usePaletteNav(menuItems, { onSelect: pick })

function submit() {
	const value = text.value.trim()
	if (!value) return
	if (value.startsWith("/")) {
		const [name, ...rest] = value.slice(1).split(" ")
		const command = COMMANDS.find((c) => c.name === name)
		if (command) {
			text.value = ""
			command.run(rest.join(" ").trim())
			return
		}
	}
	text.value = ""
	flow.send(value)
}

// rewinds prefill via the store's draft channel (also fed by per-bubble rewind)
async function rewind() {
	await flow.rewindLastUserMessage()
}

watch(
	() => flow.state.draft,
	(draft) => {
		if (draft == null) return
		text.value = draft
		flow.setDraft(null)
		nextTick(() => box.value?.focus())
	},
)

async function cwdCommand(arg) {
	const cwd = arg || (await flow.pickFolder()) // no arg: the daemon's native folder dialog
	if (!cwd) return
	flow.setCwd(cwd)
	flow.startNewChat() // the session itself is created on the first message
}

function chooseMode(mode) {
	modeMenu.value = false
	flow.setMode(mode)
}

function prefill(value) {
	text.value = value
	nextTick(() => box.value?.focus())
}

defineExpose({ prefill })
</script>
