<template>
	<div class="pointer-events-none absolute inset-x-0 bottom-0 z-10 px-5 pb-3.5">
		<div class="pointer-events-auto relative mx-auto max-w-[800px]">
			<ModelPalette
				v-if="paletteView === 'models'"
				@close="closePalettes"
				@back="openCommands"
				@providers="paletteView = 'providers'"
			/>
			<ThinkingPalette
				v-if="paletteView === 'thinking'"
				@close="closePalettes"
				@back="openCommands"
			/>
			<ProvidersDialog
				v-if="paletteView === 'providers'"
				@close="closePalettes"
				@back="openCommands"
			/>

			<!-- slash-command palette -->
			<PalettePanel v-if="menuOpen" title="Commands" :autofocus="false" @close="closePalettes">
				<div class="overflow-y-auto p-1.5">
					<template v-for="(m, i) in menuItems" :key="m.name">
						<div
							v-if="m.section"
							class="px-2.5 pb-1 text-2xs font-medium text-ink-gray-5"
							:class="i ? 'mt-1 border-t border-outline-gray-1 pt-2.5' : 'pt-1.5'"
						>
							{{ m.section }}
						</div>
						<button
							data-palette-item
							class="flex w-full items-center gap-3 rounded-5 px-2.5 py-2 text-left hover:bg-surface-gray-2"
							@click="pick(m)"
						>
							<span
								class="flex h-7 w-7 flex-none items-center justify-center rounded-5 border border-outline-gray-1 bg-surface-gray-1 text-ink-gray-6"
							>
								<FeatherIcon :name="m.icon" class="h-3.5 w-3.5" />
							</span>
							<span class="min-w-0 flex-1">
								<span class="block text-xs font-medium leading-4 text-ink-gray-9">{{ m.label }}</span>
								<span class="mt-1 block truncate text-2xs leading-4 text-ink-gray-5">{{ m.hint }}</span>
							</span>
							<code class="text-2xs text-ink-gray-4">/{{ m.name }}</code>
						</button>
					</template>
					<div v-if="!menuItems.length" class="px-3 py-8 text-center text-xs text-ink-gray-5">
						No matching commands
					</div>
				</div>
			</PalettePanel>

			<!-- queued steering -->
			<div
				v-if="flow.state.queued.length"
				class="mx-3.5 -mb-1.5 flex items-baseline gap-2 rounded-t-[10px] border border-b-0 border-outline-gray-2 bg-surface-gray-2 px-3 pb-3.5 pt-2"
			>
				<span class="flex-none text-2xs font-medium text-ink-gray-6">Queued</span>
				<span class="min-w-0 flex-1 truncate text-xs text-ink-gray-7">{{
					flow.state.queued.map((item) => item.label).join(" · ")
				}}</span>
			</div>

			<div
				class="flow-composer-surface flex flex-col gap-2 rounded-7 border border-outline-gray-2 p-2 shadow-[0_1px_2px_rgba(0,0,0,0.06),0_8px_24px_-10px_rgba(0,0,0,0.18)] dark:border-outline-gray-1"
			>
				<button
					v-if="needsCwd"
					class="flex w-full items-center gap-2.5 rounded-6 border border-dashed border-outline-gray-3 bg-surface-gray-1 px-2.5 py-2 text-left hover:bg-surface-gray-2"
					@click="chooseFolder"
				>
					<FeatherIcon name="folder" class="h-3.5 w-3.5 flex-none text-ink-gray-5" />
					<span class="min-w-0 flex-1 text-xs font-medium leading-4 text-ink-gray-9">Choose a project folder to start</span>
					<span class="flex-none text-2xs font-medium text-ink-gray-6">Browse…</span>
				</button>
				<div v-if="codeRefs.length" class="flex flex-wrap items-center gap-2 px-1 pt-0.5">
					<span
						v-for="(ref, i) in codeRefs"
						:key="`${ref.path}:${ref.start}-${ref.end}`"
						class="flex max-w-[260px] items-center gap-1.5 rounded-6 border border-outline-gray-2 bg-surface-base py-1 pl-2 pr-1"
						:title="`${ref.rel}:${ref.start}-${ref.end}`"
					>
						<FeatherIcon name="code" class="h-3 w-3 flex-none text-ink-gray-5" />
						<span class="min-w-0 truncate text-xs font-medium text-ink-gray-8">{{ refLabel(ref) }}</span>
						<button
							class="grid h-4 w-4 flex-none place-items-center rounded-4 text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-8"
							title="Remove reference"
							:disabled="submitting"
							@click="flow.removeCodeRef(i)"
						>
							<FeatherIcon name="x" class="h-3 w-3" />
						</button>
					</span>
				</div>
				<div v-if="attachments.length" class="flex flex-wrap items-start gap-2 px-1 pt-0.5">
					<template v-for="(item, i) in attachments" :key="item.key">
						<figure
							v-if="item.kind === 'image' && item.previewUrl"
							class="group/attachment relative h-[72px] w-[72px] flex-none overflow-hidden rounded-6 border border-outline-gray-2 bg-surface-base shadow-sm"
							:title="item.name"
						>
							<button
								class="block h-full w-full cursor-zoom-in"
								:aria-label="`View ${item.name}`"
								@click="viewer = item"
							>
								<img :src="item.previewUrl" :alt="item.name" class="h-full w-full object-cover" />
							</button>
							<button
								class="absolute right-1 top-1 grid h-5 w-5 place-items-center rounded-full border border-outline-gray-2 bg-surface-base/90 text-ink-gray-6 shadow-sm opacity-90 backdrop-blur-sm transition hover:bg-surface-gray-2 hover:text-ink-gray-9 group-hover/attachment:opacity-100"
								title="Remove attachment"
								:aria-label="`Remove ${item.name}`"
								:disabled="submitting"
								@click="removeAttachment(i)"
							>
								<FeatherIcon name="x" class="h-3 w-3" />
							</button>
						</figure>
						<span
							v-else
							class="flex max-w-[260px] items-center gap-2 rounded-6 border border-outline-gray-2 bg-surface-base py-1 pl-1 pr-1"
						>
							<span
								class="grid h-6 w-6 flex-none place-items-center rounded-5 border border-outline-gray-1 bg-surface-gray-1 text-ink-gray-6"
							>
								<FeatherIcon :name="item.kind === 'image' ? 'image' : 'file-text'" class="h-3.5 w-3.5" />
							</span>
							<span class="min-w-0 flex-1 truncate text-xs font-medium text-ink-gray-8">{{ item.name }}</span>
							<button
								class="grid h-5 w-5 flex-none place-items-center rounded-5 text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-8"
								title="Remove attachment"
								:aria-label="`Remove ${item.name}`"
								:disabled="submitting"
								@click="removeAttachment(i)"
							>
								<FeatherIcon name="x" class="h-3.5 w-3.5" />
							</button>
						</span>
					</template>
				</div>
				<div class="relative">
					<div
						v-if="skillPrompt"
						aria-hidden="true"
						class="pointer-events-none absolute inset-0 overflow-hidden whitespace-pre-wrap break-words px-1.5 pt-1 text-base leading-relaxed text-transparent"
					>
						<div :style="{ transform: `translateY(-${textScrollTop}px)` }">
							<span class="text-ink-blue-6">{{ skillPrompt.prefix }}</span><span class="text-ink-gray-9">{{ skillPrompt.rest }}</span>
						</div>
					</div>
					<textarea
						ref="box"
						v-model="text"
						rows="1"
						:disabled="submitting"
						placeholder="Ask flow…"
						style="caret-color: var(--ink-gray-9)"
						class="relative max-h-40 min-h-[62px] w-full resize-none border-0 bg-transparent px-1.5 pt-1 text-base leading-relaxed outline-none placeholder:text-ink-gray-4 focus:ring-0"
						:class="skillPrompt ? 'text-transparent' : 'text-ink-gray-9'"
						@keydown="onKey"
						@paste="onPaste"
						@scroll="textScrollTop = $event.currentTarget.scrollTop"
					/>
				</div>
				<input
					ref="fileInput"
					type="file"
					multiple
					accept=".png,.jpg,.jpeg,.gif,.webp,.bmp,image/png,image/jpeg,image/gif,image/webp,image/bmp"
					class="hidden"
					@change="onFilesPicked"
				/>
				<div v-if="visionWarning" class="px-1 text-2xs text-ink-amber-6">
					The selected model cannot view images. Switch to a vision-capable model before sending.
				</div>
				<div class="flex min-w-0 items-center gap-1">
					<!-- add-context menu -->
					<span class="relative flex-none">
						<button
							class="grid h-7 w-7 place-items-center rounded-5 text-ink-gray-6 hover:bg-surface-gray-2 hover:text-ink-gray-9"
							:class="plusMenu ? 'bg-surface-gray-2' : ''"
							title="Add context"
							aria-haspopup="menu"
							:aria-expanded="plusMenu"
							:disabled="submitting"
							@click="plusMenu = !plusMenu"
						>
							<FeatherIcon name="plus" class="h-4 w-4" />
						</button>
						<PopMenu :open="plusMenu" label="Add context" :width="266" @close="plusMenu = false">
							<button
								role="menuitem"
								class="flex w-full items-start gap-2.5 rounded-[10px] px-2.5 py-2 text-left hover:bg-surface-gray-2"
								@click="chooseFolder"
							>
								<FeatherIcon name="folder" class="mt-0.5 h-3.5 w-3.5 flex-none text-ink-gray-5" />
								<span class="min-w-0 flex-1">
									<span class="block text-xs font-medium leading-4 text-ink-gray-9">Project folder</span>
									<span class="mt-1 block truncate text-2xs leading-4 text-ink-gray-5" :title="flow.state.prefs.cwd ?? ''">
										{{ cwdLabel }}
									</span>
								</span>
							</button>
							<button
								role="menuitem"
								class="flex w-full items-start gap-2.5 rounded-[10px] px-2.5 py-2 text-left hover:bg-surface-gray-2"
								@click="openFilePicker"
							>
								<FeatherIcon name="paperclip" class="mt-0.5 h-3.5 w-3.5 flex-none text-ink-gray-5" />
								<span class="min-w-0 flex-1">
									<span class="block text-xs font-medium leading-4 text-ink-gray-9">Attach images</span>
									<span class="mt-1 block text-2xs leading-4 text-ink-gray-5">PNG, JPEG, GIF, WebP, or BMP</span>
								</span>
							</button>
						</PopMenu>
					</span>

					<!-- model picker: a menu of the two palettes it fronts -->
					<span class="relative min-w-0">
						<button
							class="flex h-7 min-w-0 max-w-[360px] items-center gap-1.5 rounded-5 px-2 text-xs font-medium text-ink-gray-7 hover:bg-surface-gray-2"
							:class="modelMenu ? 'bg-surface-gray-2' : ''"
							:title="`${currentModel ?? modelLabel} · thinking ${effortLabel}`"
							aria-haspopup="menu"
							:aria-expanded="modelMenu"
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
						<PopMenu :open="modelMenu" label="Model and thinking" :width="266" @close="modelMenu = false">
							<button
								v-for="entry in MODEL_MENU"
								:key="entry.view"
								role="menuitem"
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
							class="flex h-7 items-center gap-1.5 whitespace-nowrap rounded-5 px-2 text-xs font-medium text-ink-gray-7 hover:bg-surface-gray-2"
							:class="modeMenu ? 'bg-surface-gray-2' : ''"
							title="Approval mode"
							aria-haspopup="menu"
							:aria-expanded="modeMenu"
							@click="modeMenu = !modeMenu"
						>
							{{ currentMode === "auto" ? "Auto-approve" : "Ask for approval" }}
							<FeatherIcon name="chevron-down" class="h-3 w-3 flex-none text-ink-gray-4" />
						</button>
						<PopMenu :open="modeMenu" label="Approval mode" align="right" :width="266" @close="modeMenu = false">
							<button
								v-for="m in MODES"
								:key="m.id"
								role="menuitemradio"
								:aria-checked="currentMode === m.id"
								class="flex w-full items-start gap-2 rounded-[10px] px-2.5 py-2 text-left hover:bg-surface-gray-2"
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
						class="ml-1 grid h-8 w-8 flex-none place-items-center rounded-6 bg-surface-gray-10 text-ink-base shadow-sm hover:opacity-90"
						title="Stop"
						@click="flow.abort()"
					>
						<span class="h-[11px] w-[11px] rounded-[2px] bg-current" />
					</button>
					<button
						v-else
						class="ml-1 grid h-8 w-8 flex-none place-items-center rounded-6 shadow-sm"
						:class="
							canSend
								? 'bg-surface-gray-10 text-ink-base hover:opacity-90'
								: 'pointer-events-none bg-surface-gray-3 text-ink-gray-4'
						"
						title="Send"
						@click="submit"
					>
						<FeatherIcon name="arrow-up" class="h-4 w-4" />
					</button>
				</div>
			</div>
			<ImageViewer v-if="viewer" :src="viewer.previewUrl" :alt="viewer.name" @close="viewer = null" />
		</div>
	</div>
</template>

<script setup>
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue"
import FeatherIcon from "./FeatherIcon.vue"
import { dialogs as frappeDialogs } from "frappe-ui/src/utils/dialog"

import { EFFORT_LABELS, fileName } from "../transcript.js"
import ImageViewer from "./ImageViewer.vue"
import ModelPalette from "./ModelPalette.vue"
import PalettePanel from "./PalettePanel.vue"
import PopMenu from "./PopMenu.vue"
import ProvidersDialog from "./ProvidersDialog.vue"
import ThinkingPalette from "./ThinkingPalette.vue"

const flow = inject("flow")

const text = ref("")
const box = ref(null)
const fileInput = ref(null)
const attachments = ref([])
const viewer = ref(null)
const submitting = ref(false)
const textScrollTop = ref(0)
let attachmentKey = 0
let previewGeneration = 0

const SUPPORTED_IMAGE_TYPES = new Set(["image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp"])

function isSupportedImage(file) {
	const mimeType = file.type.toLowerCase()
	return SUPPORTED_IMAGE_TYPES.has(mimeType) || (!mimeType && /\.(png|jpe?g|gif|webp|bmp)$/i.test(file.name))
}

function addLocalFiles(files) {
	for (const file of files) {
		if (!isSupportedImage(file)) {
			flow.notify("Flow currently supports PNG, JPEG, GIF, WebP, and BMP images only.", "error")
			continue
		}
		if (attachments.value.some((item) => item.file && item.file.name === file.name && item.file.size === file.size)) continue
		attachments.value.push({
			key: `local:${attachmentKey++}`,
			name: file.name,
			kind: "image",
			file,
			previewUrl: URL.createObjectURL(file),
		})
	}
}

function revokePreview(item) {
	if (item?.previewUrl) URL.revokeObjectURL(item.previewUrl)
}

function clearAttachments() {
	previewGeneration++
	viewer.value = null
	for (const item of attachments.value) revokePreview(item)
	attachments.value = []
}

async function loadStoredPreviews(items, sessionId, generation) {
	await Promise.all(
		items.map(async (item) => {
			if (item.kind !== "image" || !item.id) return
			try {
				const blob = await flow.client.attachmentBlob(sessionId, item.id)
				const previewUrl = URL.createObjectURL(blob)
				const current = attachments.value.find((candidate) => candidate.key === item.key)
				if (generation !== previewGeneration || flow.state.sessionId !== sessionId || !current) {
					URL.revokeObjectURL(previewUrl)
					return
				}
				current.previewUrl = previewUrl
			} catch {
				// A missing historical attachment falls back to its compact filename badge.
			}
		}),
	)
}

function openFilePicker() {
	plusMenu.value = false
	fileInput.value?.click()
}

function onFilesPicked(event) {
	addLocalFiles([...event.target.files])
	event.target.value = ""
	// the file dialog moved focus off the textarea; typing should resume immediately
	nextTick(() => box.value?.focus())
}

function onPaste(event) {
	const images = [...(event.clipboardData?.items ?? [])]
		.filter((item) => item.kind === "file" && item.type.startsWith("image/"))
		.map((item) => item.getAsFile())
		.filter(Boolean)
	if (!images.length) return
	event.preventDefault()
	addLocalFiles(images)
}

function removeAttachment(index) {
	const [removed] = attachments.value.splice(index, 1)
	revokePreview(removed)
	nextTick(() => box.value?.focus())
}
// the palette is one stacked surface: commands is the root page, models,
// thinking and providers are sub-pages whose back arrow returns to it
const paletteView = ref(null) // null | "commands" | "models" | "thinking" | "providers"

function closePalettes() {
	paletteView.value = null
	if (text.value.startsWith("/")) text.value = ""
	nextTick(() => box.value?.focus())
}

function openCommands() {
	paletteView.value = "commands"
	if (!flow.state.sessionId) void flow.loadSkills?.()
	nextTick(() => box.value?.focus())
}

// typing a normal message dismisses a commands page left open by back-navigation
watch(text, (value) => {
	if (paletteView.value === "commands" && value && !value.startsWith("/")) paletteView.value = null
	// Preview the default catalog without creating the otherwise-lazy first session.
	if (value.startsWith("/") && !flow.state.sessionId)
		void flow.loadSkills?.()
})

// grow with content (wrapped lines included) up to the CSS max-height, then scroll
function autosize() {
	const el = box.value
	if (!el) return
	el.style.height = "auto"
	el.style.height = `${el.scrollHeight}px`
	textScrollTop.value = el.scrollTop
}
watch(text, () => nextTick(autosize))
onMounted(autosize)

// hands land on the keyboard, not the mouse: focus on load and whenever the
// conversation changes (open, switch, new chat)
onMounted(() => {
	box.value?.focus()
	window.addEventListener("keydown", onWindowKey)
})
onBeforeUnmount(() => {
	window.removeEventListener("keydown", onWindowKey)
	clearAttachments()
})
watch(
	() => flow.state.sessionId,
	() => {
		if (!submitting.value) {
			clearAttachments()
			flow.clearCodeRefs()
		}
		nextTick(() => box.value?.focus())
	},
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
	// a running session's cwd is frozen; the new folder applies from the next chat
	if (flow.state.sessionId) flow.startNewChat({ cwd: path })
	else flow.setCwd(path)
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
	{ name: "reload", label: "Reload extensions", icon: "refresh-cw", hint: "re-import server extensions", run: () => flow.reloadExtensions() },
	{ name: "abort", label: "Abort", icon: "square", hint: "interrupt the running turn", run: () => flow.abort() },
	{ name: "cwd", label: "Working directory", icon: "folder", hint: "new session in a folder: /cwd [path]", run: cwdCommand, takesArg: true },
]

const skillCommands = computed(() =>
	(flow.state.skills ?? []).map((skill) => ({
		name: `skill:${skill.name}`,
		label: skill.name,
		icon: "book-open",
		hint: skill.description,
		takesArg: true,
	})),
)
const skillPrompt = computed(() => {
	const match = text.value.match(/^\/skill:([^\s]+)(?=\s|$)/)
	if (!match || !(flow.state.skills ?? []).some((skill) => skill.name === match[1])) return null
	return { prefix: match[0], rest: text.value.slice(match[0].length) }
})
const running = computed(() => flow.state.conversation.running)
const codeRefs = computed(() => flow.state.codeRefs)
// "Add to chat" hands off to typing: pull focus as soon as a ref arrives
watch(
	() => codeRefs.value.length,
	(count, prev) => {
		if (count > (prev ?? 0)) nextTick(() => box.value?.focus())
	},
)
const refLabel = (ref) =>
	`${fileName(ref.path)} (${ref.start}${ref.end !== ref.start ? `-${ref.end}` : ""})`
const refToken = (ref) => `@${ref.rel}:${ref.start}${ref.end !== ref.start ? `-${ref.end}` : ""}`
// an existing session's cwd is frozen in its config; only new chats need one picked
const needsCwd = computed(() => !flow.state.sessionId && !flow.state.prefs.cwd)
const canSend = computed(
	() =>
		!submitting.value &&
		!needsCwd.value &&
		(text.value.trim().length > 0 || attachments.value.length > 0 || codeRefs.value.length > 0),
)

// inside a session the button reflects that session's live mode; outside, the
// preference new chats will be created with
const currentMode = computed(() => {
	if (!flow.state.sessionId) return flow.state.prefs.mode
	return flow.state.session?.config?.auto_approve ? "auto" : "ask"
})

const currentModel = computed(() => flow.state.conversation.model ?? flow.state.prefs.lastModel)
const currentEffort = computed(
	() => flow.state.conversation.reasoningEffort ?? flow.state.prefs.lastEffort ?? "default",
)
// The button shows only the final model id; routed names can have multiple
// namespace segments (for example openrouter/openai/gpt).
const modelLabel = computed(() => {
	const model = currentModel.value
	if (!model) return "choose model"
	return model.split("/").filter(Boolean).pop() || model
})
const effortLabel = computed(() => EFFORT_LABELS[currentEffort.value] ?? "Default")
const currentImageSupport = computed(() => {
	if (flow.state.sessionId && flow.state.session) return flow.state.session.supports_images
	return flow.state.models.find((item) => item.name === currentModel.value)?.supports_images
})
const visionWarning = computed(
	() => attachments.value.some((item) => item.kind === "image") && currentImageSupport.value === false,
)

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
	const commands = COMMANDS.filter((c) => c.name.startsWith(q))
	// skills match with or without the "skill:" prefix, and sit in their own section
	const skills = skillCommands.value.filter(
		(c) => c.name.startsWith(q) || c.label.startsWith(q),
	)
	return [...commands, ...skills.map((c, i) => (i === 0 ? { ...c, section: "Skills" } : c))]
})

function onKey(e) {
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
// click). Open panels and menus own Escape while they hold focus.
// e.repeat: a held key must not spam abort requests.
function onWindowKey(e) {
	if (e.key !== "Escape" || e.repeat || anyMenuOpen()) return
	if (running.value) flow.abort()
}

function pick(command) {
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

async function submit() {
	if (submitting.value) return
	const value = text.value.trim()
	if (!value && !attachments.value.length && !codeRefs.value.length) return
	if (value.startsWith("/")) {
		const [name, ...rest] = value.slice(1).split(" ")
		const command = COMMANDS.find((c) => c.name === name)
		if (command) {
			text.value = ""
			command.run(rest.join(" ").trim())
			return
		}
	}
	if (needsCwd.value) return // the composer banner points at the fix
	// code references travel as file:line tokens appended to the message
	const outgoing = [value, codeRefs.value.map(refToken).join("\n")].filter(Boolean).join("\n\n")
	const selectedAttachments = attachments.value.map((item) => ({ ...item }))
	submitting.value = true
	let sent = false
	try {
		sent = await flow.send(outgoing, selectedAttachments)
	} finally {
		submitting.value = false
		// re-enabling the disabled textarea does not restore focus on its own
		nextTick(() => box.value?.focus())
	}
	if (!sent) return
	text.value = ""
	clearAttachments()
	flow.clearCodeRefs()
}

// rewinds prefill via the store's draft channel (also fed by per-bubble rewind)
async function rewind() {
	await flow.rewindLastUserMessage()
}

watch(
	() => flow.state.draft,
	(draft) => {
		if (draft == null) return
		text.value = typeof draft === "string" ? draft : draft.text
		clearAttachments()
		const restored = (typeof draft === "string" ? [] : draft.attachments ?? []).map((item) => ({
			...item,
			key: `stored:${item.id}`,
		}))
		attachments.value = restored
		const sessionId = flow.state.sessionId
		const generation = previewGeneration
		if (sessionId) void loadStoredPreviews(restored, sessionId, generation)
		flow.setDraft(null)
		nextTick(() => box.value?.focus())
	},
)

async function cwdCommand(arg) {
	const cwd = arg || (await flow.pickFolder()) // no arg: the daemon's native folder dialog
	if (!cwd) return
	flow.startNewChat({ cwd }) // the session itself is created on the first message
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
