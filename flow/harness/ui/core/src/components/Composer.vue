<template>
	<div class="pointer-events-none absolute inset-x-0 bottom-0 z-10 px-5 pb-3.5">
		<div class="pointer-events-auto relative mx-auto max-w-[800px]">
			<ModelPalette
				v-if="paletteView === 'models'"
				:providers="has('providers')"
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
			<!-- a host's own pages, opened by its commands or toolbar pickers -->
			<slot name="palette" :view="paletteView" :close="closePalettes" :back="openCommands" />

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

			<!-- @-mention file picker -->
			<FileMentionPalette
				v-if="mentionActive"
				:query="mention.query"
				@pick="pickMention"
				@close="mentionDismissed = true"
			/>

			<!-- the pending approval rides with the composer, wherever the thread is scrolled;
			     the batch answers one call at a time, so the next call takes the card over -->
			<ApprovalCard
				v-if="approval"
				ref="card"
				:key="approval.call.id"
				:call="approval.call"
				:position="approval.position"
				:total="approval.total"
				:subagent="approval.subagent"
				class="mb-2"
			/>

			<!-- the queue: messages waiting for the run to end -->
			<div
				v-if="flow.state.queued.length"
				class="mx-3.5 -mb-1.5 flex flex-col divide-y divide-outline-gray-2 rounded-t-[10px] border border-b-0 border-outline-gray-2 bg-surface-gray-2 px-3 pb-2.5 pt-1"
			>
				<div v-for="item in flow.state.queued" :key="item.key" class="flex min-h-5 items-center gap-2 py-1">
					<span class="flex-none text-2xs font-medium text-ink-gray-6">Queued</span>
					<span class="min-w-0 flex-1 truncate text-xs text-ink-gray-7">{{ item.label }}</span>
					<!-- a compaction takes no steering: the queue waits for it to end -->
					<button
						v-if="!compacting"
						class="flex flex-none items-center gap-1 rounded-4 px-1.5 py-0.5 text-2xs font-medium text-ink-gray-7 hover:bg-surface-gray-3 hover:text-ink-gray-9"
						:title="running ? 'Add it to the running turn' : 'Send it now'"
						:disabled="disabled"
						@click="steerQueued(item)"
					>
						<FeatherIcon name="corner-down-left" class="h-3 w-3" />
						{{ running ? "Steer" : "Send" }}
					</button>
					<button
						class="grid h-5 w-5 flex-none place-items-center rounded-4 text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-9"
						title="Remove from queue"
						:disabled="disabled"
						@click="dropQueued(item)"
					>
						<FeatherIcon name="x" class="h-3 w-3" />
					</button>
				</div>
			</div>

			<!-- a fieldset: disabling it disables every control inside, a host's pickers included -->
			<fieldset
				:disabled="disabled"
				class="flow-composer-surface flex min-w-0 flex-col gap-2 rounded-7 border border-outline-gray-2 p-2 shadow-[0_1px_2px_rgba(0,0,0,0.06),0_8px_24px_-10px_rgba(0,0,0,0.18)] dark:border-outline-gray-1"
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
				<div v-if="imageTiles.length" class="flex flex-wrap gap-1.5 px-1 pt-0.5">
					<figure
						v-for="{ item, i } in imageTiles"
						:key="item.key"
						class="group/attachment relative h-[72px] w-[72px] flex-none overflow-hidden rounded-6 border border-outline-gray-2 bg-surface-base shadow-sm"
						:title="item.name"
					>
						<button class="block h-full w-full cursor-zoom-in" :aria-label="`View ${item.name}`" @click="viewer = item">
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
						<span v-if="item.preparing" class="pointer-events-none absolute bottom-1 left-1 rounded bg-surface-base/90 p-1" :aria-label="`Preparing ${item.name}`" role="status">
							<FeatherIcon name="loader" class="h-3.5 w-3.5 animate-spin" />
						</span>
					</figure>
				</div>
				<div v-if="codeRefs.length || quotes.length || fileChips.length" class="flex flex-wrap items-center gap-1.5 px-1 pt-0.5">
					<span
						v-for="(ref, i) in codeRefs"
						:key="`${ref.path}:${ref.start}-${ref.end}`"
						:class="chipClass"
						:title="`${ref.rel}:${ref.start}-${ref.end}`"
					>
						<span :class="chipIconClass"><FeatherIcon name="code" class="h-3.5 w-3.5" /></span>
						<span class="min-w-0 truncate text-xs font-medium text-ink-gray-8">{{ codeRefLabel(ref) }}</span>
						<button :class="chipRemoveClass" title="Remove reference" :disabled="submitting" @click="flow.removeCodeRef(i)">
							<FeatherIcon name="x" class="h-3 w-3" />
						</button>
					</span>
					<span v-for="(quote, i) in quotes" :key="`quote:${i}`" :class="chipClass" :title="quote">
						<span :class="chipIconClass"><FeatherIcon name="align-left" class="h-3.5 w-3.5" /></span>
						<span class="min-w-0 truncate text-xs font-medium text-ink-gray-8">{{ quoteLabel(quote) }}</span>
						<button :class="chipRemoveClass" title="Remove quote" :disabled="submitting" @click="flow.removeQuote(i)">
							<FeatherIcon name="x" class="h-3 w-3" />
						</button>
					</span>
					<span v-for="{ item, i } in fileChips" :key="item.key" :class="chipClass" :title="item.name">
						<span v-if="item.preparing" :class="chipIconClass" :aria-label="`Preparing ${item.name}`" role="status">
							<FeatherIcon name="loader" class="h-3.5 w-3.5 animate-spin" />
						</span>
						<span v-else :class="chipIconClass">
							<FeatherIcon :name="item.kind === 'image' ? 'image' : 'file-text'" class="h-3.5 w-3.5" />
						</span>
						<span class="min-w-0 flex-1 truncate text-xs font-medium text-ink-gray-8">{{ item.name }}</span>
						<button
							:class="chipRemoveClass"
							title="Remove attachment"
							:aria-label="`Remove ${item.name}`"
							:disabled="submitting"
							@click="removeAttachment(i)"
						>
							<FeatherIcon name="x" class="h-3 w-3" />
						</button>
					</span>
				</div>
				<div v-for="item in attachments.filter((item) => item.error)" :key="item.key" class="px-1 text-xs text-ink-red-6">
					Could not prepare {{ item.name }}: {{ item.error }}
					<button class="underline" :disabled="submitting" :aria-label="`Retry ${item.name}`" @click="prepareAttachment(item)">Retry</button>
				</div>
				<!-- 16px on phones: iPhone Safari zooms into smaller fields (the overlay mirrors the box) -->
				<div class="relative">
					<div
						v-if="skillParts"
						aria-hidden="true"
						class="pointer-events-none absolute inset-0 overflow-hidden whitespace-pre-wrap break-words px-1.5 pt-1 text-base leading-relaxed text-transparent max-sm:text-[16px]"
					>
						<div :style="{ transform: `translateY(-${textScrollTop}px)` }">
							<span v-for="(part, i) in skillParts" :key="i" :class="part.skill ? 'text-ink-blue-6' : 'text-ink-gray-9'">{{ part.text }}</span>
						</div>
					</div>
					<textarea
						ref="box"
						v-model="text"
						rows="1"
						:disabled="submitting"
						:placeholder="placeholder"
						style="caret-color: var(--ink-gray-9)"
						class="relative max-h-40 min-h-[62px] w-full resize-none border-0 bg-transparent px-1.5 pt-1 text-base leading-relaxed outline-none placeholder:text-ink-gray-4 focus:ring-0 max-sm:text-[16px]"
						:class="skillParts ? 'text-transparent' : 'text-ink-gray-9'"
						@keydown="onKey"
						@paste="onPaste"
						@scroll="textScrollTop = $event.currentTarget.scrollTop"
						@input="syncCaret"
						@keyup="syncCaret"
						@click="syncCaret"
						@select="syncCaret"
					/>
				</div>
				<input
					ref="fileInput"
					type="file"
					multiple
					:accept="imagesOnly ? IMAGE_ACCEPT : undefined"
					class="hidden"
					@change="onFilesPicked"
				/>
				<div v-if="visionWarning" class="px-1 text-2xs text-ink-amber-6">
					The selected model cannot view images. Switch to a vision-capable model before sending.
				</div>
				<div class="flex min-w-0 items-center gap-1">
					<!-- attach files -->
					<button
						class="grid h-7 w-7 flex-none place-items-center rounded-5 text-ink-gray-6 hover:bg-surface-gray-2 hover:text-ink-gray-9"
						:title="imagesOnly ? 'Attach images' : 'Attach files'"
						:disabled="submitting"
						@click="openFilePicker"
					>
						<FeatherIcon name="plus" class="h-4 w-4" />
					</button>

					<!-- the pickers; a host adds its own around the model button -->
					<slot name="toolbar" :open-palette="openPalette">
						<ModelButton @open="openPalette" />
					</slot>

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
							{{ modeLabel }}
							<FeatherIcon name="chevron-down" class="h-3 w-3 flex-none text-ink-gray-4" />
						</button>
						<PopMenu :open="modeMenu" label="Approval mode" align="right" :width="266" @close="modeMenu = false">
							<button
								v-for="m in modes"
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
						v-if="running && !submitting"
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
							canSend || submitting
								? 'bg-surface-gray-10 text-ink-base hover:opacity-90'
								: 'pointer-events-none bg-surface-gray-3 text-ink-gray-4'
						"
						title="Send"
						:disabled="!canSend"
						:aria-busy="submitting"
						@click="submit"
					>
						<FeatherIcon v-if="submitting" name="loader" class="h-4 w-4 animate-spin" />
						<FeatherIcon v-else name="arrow-up" class="h-4 w-4" />
					</button>
				</div>
			</fieldset>
			<ImageViewer v-if="viewer" :src="viewer.previewUrl" :alt="viewer.name" @close="viewer = null" />
		</div>
	</div>
</template>

<script setup>
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue"
import FeatherIcon from "./FeatherIcon.vue"
import { dialogs as frappeDialogs } from "frappe-ui/src/utils/dialog"

import {
	APPROVAL_MODES,
	approvalToAnswer,
	codeRefLabel,
	quoteBlock,
	skillSegments,
	splitCodeRefs,
	splitQuotes,
	subagentTitle,
} from "../transcript.js"
import ApprovalCard from "./ApprovalCard.vue"
import FileMentionPalette from "./FileMentionPalette.vue"
import ImageViewer from "./ImageViewer.vue"
import ModelButton from "./ModelButton.vue"
import ModelPalette from "./ModelPalette.vue"
import PalettePanel from "./PalettePanel.vue"
import PopMenu from "./PopMenu.vue"
import ProvidersDialog from "./ProvidersDialog.vue"
import ThinkingPalette from "./ThinkingPalette.vue"

// Hosts without a filesystem trim the composer to what their client serves.
const props = defineProps({
	// slash commands offered, in order: names, or a host's own { name, label, icon, hint, view }
	// that opens its palette slot on `view`; null = all built-ins
	commands: { type: Array, default: null },
	mentions: { type: Boolean, default: true }, // "@" file mentions
	// the daemon stores images only; a host that stages uploads itself takes any file
	imagesOnly: { type: Boolean, default: true },
	placeholder: { type: String, default: "Ask flow…" },
	modes: { type: Array, default: () => APPROVAL_MODES }, // [{ id, label, desc }] in the host's words
	disabled: { type: Boolean, default: false }, // shown but inert, e.g. until the host's setup is done
})

const flow = inject("flow")
const skillsEnabled = computed(() => flow.options.skillsEnabled !== false)

const text = ref("")
const box = ref(null)
const fileInput = ref(null)
const attachments = ref([])
const viewer = ref(null)
const submitting = ref(false)
const textScrollTop = ref(0)
const caretPos = ref(0)
const mentionDismissed = ref(false)
let attachmentKey = 0
let previewGeneration = 0
const preparations = new Map()
let preparationQueue = Promise.resolve()

const SUPPORTED_IMAGE_TYPES = new Set(["image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp"])
const IMAGE_ACCEPT = ".png,.jpg,.jpeg,.gif,.webp,.bmp,image/png,image/jpeg,image/gif,image/webp,image/bmp"

// the store owns the cap; blocking here just makes it visible before send time
function atAttachmentLimit() {
	const { maxAttachments } = flow.options
	if (attachments.value.length < maxAttachments) return false
	flow.notify(`A message can carry at most ${maxAttachments} attachments.`, "error")
	return true
}

function isSupportedImage(file) {
	const mimeType = file.type.toLowerCase()
	return SUPPORTED_IMAGE_TYPES.has(mimeType) || (!mimeType && /\.(png|jpe?g|gif|webp|bmp)$/i.test(file.name))
}

function addLocalFiles(files) {
	for (const file of files) {
		if (atAttachmentLimit()) return
		const image = isSupportedImage(file)
		if (props.imagesOnly && !image) {
			flow.notify("Flow currently supports PNG, JPEG, GIF, WebP, and BMP images only.", "error")
			continue
		}
		if (attachments.value.some((item) => item.file && item.file.name === file.name && item.file.size === file.size)) continue
		attachments.value.push({
			key: `local:${attachmentKey++}`,
			name: file.name,
			kind: image ? "image" : "file",
			file,
			previewUrl: image ? URL.createObjectURL(file) : null,
		})
		if (flow.prepareAttachment) void prepareAttachment(attachments.value.at(-1))
	}
}

function discardAttachment(item) {
	if (item.id && item.file && flow.discardAttachments) {
		void flow.discardAttachments([item.id]).catch(() => {})
	}
}

function prepareAttachment(item) {
	if (preparations.has(item.key)) return preparations.get(item.key)
	item.preparing = true
	item.error = null
	// Avoid running OCR for a whole batch of large files at once.
	const pending = preparationQueue.then(async () => {
		try {
			if (!attachments.value.includes(item)) return
			const prepared = await flow.prepareAttachment(item.file, currentModel.value)
			Object.assign(item, prepared)
			if (!attachments.value.includes(item)) discardAttachment(item)
		} catch (error) {
			item.error = error.message || "Please try again."
		} finally {
			item.preparing = false
			preparations.delete(item.key)
		}
	})
	preparationQueue = pending
	preparations.set(item.key, pending)
	return pending
}

function revokePreview(item) {
	if (item?.previewUrl) URL.revokeObjectURL(item.previewUrl)
}

function clearAttachments(discard = true) {
	previewGeneration++
	viewer.value = null
	for (const item of attachments.value) {
		revokePreview(item)
		if (discard) discardAttachment(item)
	}
	attachments.value = []
}

async function loadStoredPreviews(items, sessionId, generation) {
	await Promise.all(
		items.map(async (item) => {
			if (item.kind !== "image" || !item.id) return
			const previewUrl = await flow.attachmentPreview(sessionId, item.id)
			if (!previewUrl) return
			const current = attachments.value.find((candidate) => candidate.key === item.key)
			if (generation !== previewGeneration || flow.state.sessionId !== sessionId || !current) {
				URL.revokeObjectURL(previewUrl)
				return
			}
			current.previewUrl = previewUrl
		}),
	)
}

function openFilePicker() {
	fileInput.value?.click()
}

function onFilesPicked(event) {
	addLocalFiles([...event.target.files])
	event.target.value = ""
	// the file dialog moved focus off the textarea; typing should resume immediately
	nextTick(() => box.value?.focus())
}

function onPaste(event) {
	const data = event.clipboardData
	const images = [...(data?.items ?? [])]
		.filter((item) => item.kind === "file" && item.type.startsWith("image/"))
		.map((item) => item.getAsFile())
		.filter(Boolean)
	if (!images.length) return
	// a spreadsheet or document range brings a picture of itself along: the text is what was
	// copied. A copied file or web image has no text in its HTML.
	if (data.getData("text/plain").trim() && data.getData("text/html").replace(/<[^>]*>/g, "").trim()) return
	event.preventDefault()
	addLocalFiles(images)
}

function removeAttachment(index) {
	const [removed] = attachments.value.splice(index, 1)
	revokePreview(removed)
	discardAttachment(removed)
	nextTick(() => box.value?.focus())
}

// plain DOM selectionStart reads aren't reactive on their own (arrow keys, clicks) —
// resync it explicitly so the @-mention computed below can see caret moves
function syncCaret() {
	caretPos.value = box.value?.selectionStart ?? text.value.length
}

// the word being typed when it starts with `sigil`: the nearest one at or before the
// caret that starts a word (line/word start, or preceded by whitespace) with no
// whitespace between it and the caret
function wordAtCaret(sigil) {
	const head = text.value.slice(0, caretPos.value)
	const at = head.lastIndexOf(sigil)
	if (at === -1) return null
	const query = head.slice(at + 1)
	if (/\s/.test(query)) return null
	if (at > 0 && !/\s/.test(head[at - 1])) return null
	return { start: at, query }
}

// an active @-mention
const mention = computed(() => (props.mentions ? wordAtCaret("@") : null))
const mentionActive = computed(() => !!mention.value && !mentionDismissed.value)
// a fresh "@" re-arms the picker even if a previous one was dismissed with Escape
watch(
	() => mention.value?.start,
	(start) => {
		if (start !== undefined) mentionDismissed.value = false
	},
)

function pickMention(path) {
	const m = mention.value
	if (!m) return
	// remove the whole "@word" the caret sits in, not just its "@"-to-caret prefix —
	// picking mid-word (caret moved back into the query) must not strand the tail
	const queryEnd = m.start + 1 + m.query.length
	const tailLength = text.value.slice(queryEnd).match(/^\S*/)[0].length
	text.value = text.value.slice(0, m.start) + text.value.slice(queryEnd + tailLength)
	if (!attachments.value.some((item) => item.mentionPath === path) && !atAttachmentLimit()) {
		attachments.value.push({
			key: `mention:${attachmentKey++}`,
			name: path,
			kind: "file",
			mentionPath: path,
		})
	}
	nextTick(() => {
		box.value?.focus()
		box.value?.setSelectionRange(m.start, m.start)
		syncCaret()
	})
}

// the palette is one stacked surface: commands is the root page, models,
// thinking and providers are sub-pages whose back arrow returns to it
const paletteView = ref(null) // null | "commands" | "models" | "thinking" | "providers"

function closePalettes() {
	paletteView.value = null
	if (slash.value) slashDismissed.value = true
	nextTick(() => box.value?.focus())
}

function openCommands() {
	paletteView.value = "commands"
	if (skillsEnabled.value) void flow.loadSkills?.()
	nextTick(() => box.value?.focus())
}

// typing a normal message dismisses a commands page left open by back-navigation
watch(text, (value) => {
	if (paletteView.value === "commands" && value && !slash.value) paletteView.value = null
	// Load the invocable skills; without a session this previews without creating one.
	if (skillsEnabled.value && (slash.value || value.includes("/skill:"))) void flow.loadSkills?.()
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
	clearAttachments(!submitting.value)
})
watch(
	() => flow.state.sessionId,
	() => {
		if (!submitting.value) {
			clearAttachments()
			flow.clearCodeRefs()
			flow.clearQuotes()
		}
		nextTick(() => box.value?.focus())
	},
)

const modeMenu = ref(false)

function openPalette(view) {
	paletteView.value = view
}

async function chooseFolder() {
	const path = await flow.pickFolder()
	if (!path) return
	// a running session's cwd is frozen; the new folder applies from the next chat
	if (flow.state.sessionId) flow.startNewChat({ cwd: path })
	else flow.setCwd(path)
}

const COMMANDS = [
	{ name: "model", label: "Model", icon: "cpu", hint: "choose the model", stacked: true, run: () => (paletteView.value = "models") },
	{ name: "thinking", label: "Thinking", icon: "zap", hint: "set the reasoning effort", stacked: true, run: () => (paletteView.value = "thinking") },
	{ name: "providers", label: "Providers", icon: "key", hint: "connect model providers", stacked: true, run: () => (paletteView.value = "providers") },
	{ name: "settings", label: "Settings", icon: "settings", hint: "custom instructions, defaults and theme", run: () => flow.setSettingsOpen(true) },
	{ name: "transcript", label: "Transcript", icon: "list", hint: "every step and what it cost in tokens", run: () => flow.setTranscriptOpen(true) },
	{ name: "new", label: "New chat", icon: "plus", hint: "start a fresh conversation", run: () => flow.startNewChat() },
	{ name: "rewind", label: "Rewind", icon: "rotate-ccw", hint: "branch from before your last message", run: rewind },
	{ name: "compact", label: "Compact", icon: "minimize-2", hint: "summarize and shrink context", run: () => flow.compact() },
	{ name: "reload", label: "Reload extensions", icon: "refresh-cw", hint: "re-import server extensions", run: () => flow.reloadExtensions() },
	{ name: "abort", label: "Abort", icon: "square", hint: "interrupt the running turn", run: () => flow.abort() },
	{ name: "cwd", label: "Working directory", icon: "folder", hint: "new session in a folder: /cwd [path]", run: cwdCommand, takesArg: true },
]
const enabledCommands = computed(() =>
	(props.commands
		? props.commands
				.map((entry) =>
					typeof entry === "string"
						? COMMANDS.find((c) => c.name === entry)
						: { ...entry, stacked: true, run: () => (paletteView.value = entry.view) },
				)
				.filter(Boolean)
		: COMMANDS).filter((command) => command.name !== "rewind" || flow.capabilities?.rewind),
)
const has = (name) => enabledCommands.value.some((c) => c.name === name)

const skillCommands = computed(() =>
	(skillsEnabled.value ? flow.state.skills ?? [] : []).map((skill) => ({
		name: `skill:${skill.name}`,
		label: skill.name,
		icon: "book-open",
		hint: skill.description,
		skill: true,
	})),
)
// known skill commands show in blue wherever they sit
const skillParts = computed(() => {
	if (!skillsEnabled.value) return null
	const parts = skillSegments(text.value, (flow.state.skills ?? []).map((skill) => skill.name))
	return parts.some((part) => part.skill) ? parts : null
})
const running = computed(() => flow.state.conversation.running)
const compacting = computed(() => flow.state.conversation.compacting)
const approval = computed(() => {
	const conversation = flow.state.conversation
	const pending = approvalToAnswer(conversation)
	const index = pending?.calls.findIndex((call) => !(call.id in pending.answers)) ?? -1
	if (index === -1) return null
	return {
		call: pending.calls[index],
		position: index + 1,
		total: pending.calls.length,
		// a sub-agent's question says which sub-agent asks
		subagent: pending.subagentId ? (subagentTitle(conversation, pending.subagentId) ?? "") : null,
	}
})
// an answered call takes its card away, and the keyboard focus inside it: the box gets that
const card = ref(null)
watch(
	() => approval.value?.call.id,
	() => {
		if (card.value?.$el.contains(document.activeElement)) nextTick(() => box.value?.focus())
	},
)
const codeRefs = computed(() => flow.state.codeRefs)
const quotes = computed(() => flow.state.quotes)
const quoteLabel = (quote) => quote.replace(/\s+/g, " ").slice(0, 120)
// "Add to chat" hands off to typing: pull focus as soon as a ref or quote arrives
watch(
	() => codeRefs.value.length + quotes.value.length,
	(count, prev) => {
		if (count > (prev ?? 0)) nextTick(() => box.value?.focus())
	},
)
const refToken = (ref) => `@${ref.rel}:${ref.start}${ref.end !== ref.start ? `-${ref.end}` : ""}`
// images stage as full previews on their own row; code refs and files share one row of chips
const isImageTile = (item) => item.kind === "image" && !!item.previewUrl
const staged = (keep) => attachments.value.map((item, i) => ({ item, i })).filter(({ item }) => keep(item))
const imageTiles = computed(() => staged(isImageTile))
const fileChips = computed(() => staged((item) => !isImageTile(item)))
const chipClass = "flex h-8 max-w-[260px] items-center gap-2 rounded-6 border border-outline-gray-2 bg-surface-base pl-1 pr-1"
const chipIconClass = "grid h-6 w-6 flex-none place-items-center rounded-5 bg-surface-gray-1 text-ink-gray-6"
const chipRemoveClass =
	"grid h-5 w-5 flex-none place-items-center rounded-5 text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-8"
// an existing session's cwd is frozen in its config; only new chats need one picked
const needsCwd = computed(() => flow.options.requireCwd && !flow.state.sessionId && !flow.state.prefs.cwd)
const canSend = computed(
	() =>
		!submitting.value &&
		!needsCwd.value &&
		(text.value.trim().length > 0 || attachments.value.length > 0 || codeRefs.value.length > 0 || quotes.value.length > 0),
)

// inside a session the button reflects that session's live mode; outside, the
// preference new chats will be created with
const currentMode = computed(() => {
	if (!flow.state.sessionId) return flow.state.prefs.mode
	return flow.state.session?.config?.auto_approve ? "auto" : "ask"
})
const modeLabel = computed(() => props.modes.find((m) => m.id === currentMode.value)?.label ?? currentMode.value)

const currentModel = computed(() => flow.state.conversation.model ?? flow.state.prefs.lastModel)
const currentImageSupport = computed(() => {
	if (flow.state.sessionId && flow.state.session) return flow.state.session.supports_images
	return flow.state.models.find((item) => item.name === currentModel.value)?.supports_images
})
const visionWarning = computed(
	() =>
		props.imagesOnly &&
		attachments.value.some((item) => item.kind === "image") &&
		currentImageSupport.value === false,
)

// slash palette: the "/word" being typed anywhere, or a sub-page navigated back
// to the commands root. A space ("/cwd ") ends the word — the menu closes so
// Enter submits the command instead of re-picking it forever.
const slash = computed(() => wordAtCaret("/"))
const slashDismissed = ref(false)
// a fresh "/" re-arms the menu even if a previous one was dismissed with Escape
watch(
	() => slash.value?.start,
	(start) => {
		if (start !== undefined) slashDismissed.value = false
	},
)
const atStart = (index) => !text.value.slice(0, index).trim()
// mid-message only skills are offered: they are part of the message, commands act on the app
const slashMidMessage = computed(() => !!slash.value && !atStart(slash.value.start))
const matches = computed(() => {
	const q = (slash.value?.query ?? "").toLowerCase()
	const commands = slashMidMessage.value ? [] : enabledCommands.value.filter((c) => c.name.startsWith(q))
	// skills match with or without the "skill:" prefix, and sit in their own section
	const skills = skillCommands.value.filter(
		(c) => c.name.startsWith(q) || c.label.startsWith(q),
	)
	return [...commands, ...skills.map((c, i) => (i === 0 ? { ...c, section: "Skills" } : c))]
})
// mid-message, a "/" no skill matches (a path, a fraction) opens nothing
const menuOpen = computed(
	() =>
		paletteView.value === "commands" ||
		(!!slash.value && !slashDismissed.value && (!slashMidMessage.value || matches.value.length > 0)),
)
const menuItems = computed(() => (menuOpen.value ? matches.value : []))

// An IME's Enter picks a candidate and its Escape drops one; Safari sends the closing key
// after compositionend, marked only by keyCode 229.
const composing = (e) => e.isComposing || e.keyCode === 229

function onKey(e) {
	if (composing(e)) return
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
			mentionDismissed.value = true
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
		mentionActive.value ||
		modeMenu.value ||
		frappeDialogs.value.length
	)
}

// Escape aborts even when focus is outside the textarea (reading, after a
// click). Open panels and menus own Escape while they hold focus, and so do
// dialogs and other fields (a search box, a form, the editor).
// e.repeat: a held key must not spam abort requests.
function onWindowKey(e) {
	if (e.key !== "Escape" || e.repeat || e.defaultPrevented || composing(e) || anyMenuOpen()) return
	if (e.target?.closest?.('input, textarea, select, [contenteditable], [role="dialog"], [role="menu"]')) return
	if (running.value) flow.abort()
}

function pick(command) {
	// a skill goes into the message; a command opening it waits for its argument
	if (command.skill || (command.takesArg && atStart(slashRange()[0]))) {
		paletteView.value = null
		replaceSlash(`/${command.name} `)
		return
	}
	if (slash.value) replaceSlash("")
	// stacked commands swap to their sub-page (run assigns it); the rest close
	if (!command.stacked) paletteView.value = null
	command.run()
}

// the whole "/word" at the caret (like pickMention), or just the caret when the
// list was reopened from a sub-page
function slashRange() {
	const s = slash.value
	if (!s) return [caretPos.value, caretPos.value]
	const queryEnd = s.start + 1 + s.query.length
	return [s.start, queryEnd + text.value.slice(queryEnd).match(/^\S*/)[0].length]
}

// put `value` in that range as a word of its own, taking the space after it
function replaceSlash(value) {
	const [start, end] = slashRange()
	const before = text.value.slice(0, start)
	const head = before + (value && /\S$/.test(before) ? " " : "") + value
	text.value = head + text.value.slice(end).replace(/^ /, "")
	caretPos.value = head.length
	nextTick(() => {
		box.value?.focus()
		box.value?.setSelectionRange(head.length, head.length)
	})
}

async function submit() {
	if (submitting.value) return
	const draftText = text.value
	const value = draftText.trim()
	if (!value && !attachments.value.length && !codeRefs.value.length && !quotes.value.length) return
	if (value.startsWith("/")) {
		const [name, ...rest] = value.slice(1).split(" ")
		const command = enabledCommands.value.find((c) => c.name === name)
		if (command) {
			text.value = ""
			command.run(rest.join(" ").trim())
			return
		}
	}
	if (needsCwd.value) return // the composer banner points at the fix
	// quotes travel as blockquotes under the message, code references as file:line tokens after them
	const selectedQuotes = [...quotes.value]
	const selectedCodeRefs = [...codeRefs.value]
	const outgoing = [value, selectedQuotes.map(quoteBlock).join("\n\n"), selectedCodeRefs.map(refToken).join("\n")]
		.filter(Boolean)
		.join("\n\n")
	const selectedAttachments = [...attachments.value]
	const sendingSessionId = flow.state.sessionId
	submitting.value = true
	try {
		const pending = selectedAttachments.map((item) => preparations.get(item.key)).filter(Boolean)
		if (pending.length) await Promise.all(pending)
		if (flow.state.sessionId !== sendingSessionId) return
		if (selectedAttachments.some((item) => item.error || !attachments.value.includes(item))) return
		// the box and its chips empty as the bubble appears; a send that never lands hands
		// them back rather than losing them. Only what went out: a ref or quote added
		// meanwhile stays staged.
		text.value = ""
		attachments.value = attachments.value.filter((item) => !selectedAttachments.includes(item))
		flow.clearCodeRefs(selectedCodeRefs)
		flow.clearQuotes(selectedQuotes)
		if (await flow.send(outgoing, selectedAttachments)) {
			for (const item of selectedAttachments) revokePreview(item)
		} else {
			text.value = draftText
			attachments.value = [...selectedAttachments, ...attachments.value]
			for (const ref of selectedCodeRefs) flow.addCodeRef(ref.path, ref.start, ref.end)
			for (const quote of selectedQuotes) flow.addQuote(quote)
		}
	} finally {
		submitting.value = false
		// re-enabling the disabled textarea does not restore focus on its own
		nextTick(() => box.value?.focus())
	}
}

// rewinds prefill via the store's draft channel (also fed by per-bubble rewind)
async function rewind() {
	await flow.rewindLastUserMessage()
}

watch(
	() => flow.state.draft,
	(draft) => {
		if (draft == null) return
		// its quotes and code references come back as chips, not as their tokens
		const { body, refs } = splitCodeRefs(typeof draft === "string" ? draft : draft.text)
		const { body: plain, quotes: quoted } = splitQuotes(body)
		text.value = plain
		caretPos.value = plain.length
		flow.clearCodeRefs()
		flow.clearQuotes()
		for (const ref of refs) flow.addCodeRef(ref.path, ref.start, ref.end)
		for (const quote of quoted) flow.addQuote(quote)
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

// the queue's buttons hand the cursor back to the box
function steerQueued(item) {
	flow.sendQueued(item)
	box.value?.focus()
}

function dropQueued(item) {
	flow.removeQueued(item)
	box.value?.focus()
}

function chooseMode(mode) {
	modeMenu.value = false
	flow.setMode(mode)
}

function prefill(value) {
	text.value = value
	caretPos.value = value.length
	nextTick(() => box.value?.focus())
}

defineExpose({ prefill })
</script>
