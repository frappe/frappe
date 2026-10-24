<template>
	<!-- form: scrolling body, pinned actions -->
	<div v-if="draft" class="flex min-h-0 flex-1 flex-col">
		<div class="min-h-0 flex-1 overflow-y-auto px-4 pt-3 sm:px-8 md:pt-8">
			<div class="flex items-center gap-2">
				<button v-if="!headerBack" class="flow-icon-btn -my-1 -ml-1.5" title="Back to presets" @click="back">
					<FeatherIcon name="arrow-left" class="h-4 w-4" />
				</button>
				<h2 class="text-base font-semibold text-ink-gray-9">{{ draft.default ? "Standard preset" : draft.id ? "Edit preset" : "New preset" }}</h2>
			</div>

			<div class="mt-6 flex flex-col gap-5 pb-6">
				<TextInput v-if="!draft.default" v-model="draft.name" label="Name" placeholder="Reviewer" autofocus />

				<div>
					<div class="text-sm font-medium text-ink-gray-9">Tools</div>
					<p v-if="!flow.state.tools.length" class="mt-1.5 text-xs text-ink-gray-5">The daemon did not report any tools.</p>
					<div v-else class="mt-2 max-h-64 divide-y divide-outline-gray-1 overflow-y-auto rounded-6 border border-outline-gray-2">
						<template v-for="group in toolGroups" :key="group.key">
							<div v-if="group.label" class="bg-surface-gray-1 px-4 py-1.5 text-2xs font-medium text-ink-gray-5">{{ group.label }}</div>
							<label
								v-for="tool in group.tools"
								:key="tool.name"
								class="flex cursor-pointer items-center gap-3 px-4 py-3.5 first:rounded-t-6 last:rounded-b-6 hover:bg-surface-gray-1"
							>
								<Checkbox
									:model-value="draft[group.key].includes(tool.name)"
									:disabled="locked(tool)"
									@update:model-value="toggleTool(group.key, tool.name, $event)"
								/>
								<span class="w-20 flex-none text-xs font-medium text-ink-gray-9">{{ tool.name }}</span>
								<span class="min-w-0 flex-1 truncate text-xs text-ink-gray-5">{{ tool.description }}</span>
							</label>
						</template>
					</div>
				</div>

				<div v-if="!draft.default">
					<div class="text-sm font-medium text-ink-gray-9">Prompt</div>
					<div class="mt-2 grid grid-cols-2 gap-2">
						<button
							v-for="option in PROMPT_MODES"
							:key="option.value"
							class="flex flex-col items-start rounded-5 border px-3 py-2.5 text-left hover:bg-surface-gray-1"
							:class="draft.promptMode === option.value ? 'border-outline-gray-4 bg-surface-gray-1' : 'border-outline-gray-2'"
							@click="draft.promptMode = option.value"
						>
							<span class="block text-xs font-medium text-ink-gray-9">{{ option.label }}</span>
							<span class="mt-0.5 block text-xs leading-5 text-ink-gray-5">{{ option.desc }}</span>
						</button>
					</div>
					<Textarea
						v-model="draft.prompt"
						class="mt-3"
						:rows="7"
						placeholder="You are a careful reviewer."
					/>
				</div>
			</div>
		</div>

		<div class="flex items-center justify-end gap-3 border-t border-outline-gray-1 px-4 py-4 sm:px-8">
			<span v-if="dirty" class="text-xs text-ink-gray-5">Unsaved changes</span>
			<Button v-if="draft.id" label="Delete" variant="ghost" theme="red" @click="confirmDelete" />
			<Button variant="solid" label="Save" :disabled="!dirty || (!draft.default && !draft.name.trim())" @click="save" />
		</div>
	</div>

	<!-- list -->
	<div v-else class="min-h-0 flex-1 overflow-y-auto px-4 pb-10 pt-3 sm:px-8 md:pt-8">
		<div class="flex items-start justify-between gap-4">
			<div>
				<h2 class="text-base font-semibold text-ink-gray-9">Agent presets</h2>
				<p class="mt-1 text-xs leading-5 text-ink-gray-6">
					{{ inSession ? "This chat keeps the preset it started with. Start a new chat to switch." : "Saved setups for new chats. Pick the one to use." }}
				</p>
			</div>
			<Button v-if="!layout.narrow" variant="solid" label="New preset" @click="draft = blank()" />
		</div>

		<div class="mt-6 divide-y divide-outline-gray-1 rounded-6 border border-outline-gray-2">
			<div
				v-for="row in listRows"
				:key="row.id ?? 'default'"
				class="flex items-center gap-4 px-4 py-3 first:rounded-t-6 last:rounded-b-6"
				:class="row.active ? 'bg-surface-gray-1' : ''"
			>
				<button
					class="flex min-w-0 flex-1 items-center gap-3 text-left disabled:cursor-not-allowed disabled:opacity-60"
					:disabled="inSession"
					@click="flow.setActivePreset(row.id)"
				>
					<span
						class="h-4 w-4 flex-none rounded-full border"
						:class="row.active ? 'border-4 border-outline-gray-5' : 'border-outline-gray-4'"
					/>
					<span class="min-w-0 flex-1">
						<span class="block text-sm font-medium text-ink-gray-9">{{ row.name }}</span>
						<span class="mt-1 block truncate text-xs text-ink-gray-6">{{ row.summary }}</span>
					</span>
				</button>
				<button class="flow-icon-btn" title="Edit preset" @click="row.preset ? edit(row.preset) : editDefault()">
					<FeatherIcon name="edit" class="h-4 w-4" />
				</button>
			</div>
		</div>
		<!-- a narrow frame has no room beside the heading: the button ends the page -->
		<Button v-if="layout.narrow" class="mt-4" variant="solid" label="New preset" @click="draft = blank()" />
	</div>
</template>

<script setup>
import { computed, inject, ref } from "vue"
import { Button } from "frappe-ui/src/components/Button"
import { Checkbox } from "frappe-ui/src/components/Checkbox"
import { TextInput } from "frappe-ui/src/components/TextInput"
import { Textarea } from "frappe-ui/src/components/Textarea"
import { dialog } from "frappe-ui/src/utils/dialog"
import FeatherIcon from "./FeatherIcon.vue"

import { layout } from "../layout.js"
import { useSettingsBack } from "../settingsBack.js"

const flow = inject("flow")

const PROMPT_MODES = [
	{ value: "append", label: "Add to the default prompt", desc: "Keeps Flow's built-in guidance and adds yours." },
	{ value: "replace", label: "Replace the default prompt", desc: "Drops the built-in guidance. Project context and skills stay." },
]

// a preset is read once, when a chat is created, so switching is only offered on a blank chat
const inSession = computed(() => !!flow.state.sessionId)
const draft = ref(null)
const headerBack = useSettingsBack(() => !!draft.value, back)
let opened = null // the draft as opened, for the dirty check

const extensionNames = computed(() => flow.state.tools.filter((t) => t.extension).map((t) => t.name))
// built-ins and extension tools are separate lists on a preset, matching the session config
const toolGroups = computed(() =>
	[
		{ key: "tools", tools: flow.state.tools.filter((t) => !t.extension) },
		{ key: "extensionTools", label: "Extensions", tools: flow.state.tools.filter((t) => t.extension) },
	].filter((group) => group.tools.length),
)
// the Default preset always has the core tools; only bundled and extension tools are a choice there
const locked = (tool) => draft.value.default && !tool.bundled && !tool.extension

const dirty = computed(() => !!draft.value && JSON.stringify(draft.value) !== opened)

const listRows = computed(() => {
	// inside a chat, mark the preset that chat was created with, not the pick for new chats
	const wanted = inSession.value ? flow.state.session?.config?.preset : flow.state.prefs.activePreset
	const active = flow.state.presets.some((p) => p.id === wanted) ? wanted : null
	return [
		{ id: null, name: "Standard", summary: defaultSummary(), active: !active },
		...flow.state.presets.map((p) => ({ id: p.id, name: p.name, summary: summary(p), active: p.id === active, preset: p })),
	]
})

// without a tool list there is nothing to count, so describe the daemon's defaults instead
function defaultSummary() {
	return flow.state.tools.length ? summary(defaultPreset()) : "Core tools and the built-in prompt."
}

function summary(preset) {
	const total = flow.state.tools.length
	const enabled = preset.tools.length + (preset.extensionTools ?? extensionNames.value).length
	return [
		total ? `${enabled} of ${total} tools` : `${enabled} tools`,
		preset.prompt?.trim() ? (preset.promptMode === "replace" ? "Replaces prompt" : "Adds to prompt") : null,
	]
		.filter(Boolean)
		.join(" · ")
}

// what a chat gets with no preset: core tools and every extension on, bundled tools off
function daemonDefaults() {
	return {
		tools: flow.state.tools.filter((t) => !t.extension && !t.bundled).map((t) => t.name),
		extensionTools: extensionNames.value,
	}
}

// the Default preset as chats get it
function defaultPreset() {
	return flow.defaultPreset() ?? daemonDefaults()
}

function blank() {
	return openDraft({ name: "", ...daemonDefaults(), promptMode: "append", prompt: "" })
}

function editDefault() {
	draft.value = openDraft({ default: true, ...defaultPreset() })
}

function edit(preset) {
	draft.value = openDraft({
		...preset,
		tools: [...preset.tools],
		extensionTools: [...(preset.extensionTools ?? extensionNames.value)], // older presets predate the choice
	})
}

function openDraft(value) {
	opened = JSON.stringify(value)
	return value
}

// opened by the composer's "Create a preset": on a blank one
if (flow.takeNewPreset()) draft.value = blank()

function toggleTool(key, name, on) {
	const names = draft.value[key].filter((t) => t !== name)
	draft.value[key] = on ? [...names, name] : names
}

// stays on the form, reopened as saved
function save() {
	if (draft.value.default) {
		flow.saveDefaultPreset(draft.value)
		editDefault()
	} else {
		const id = flow.savePreset({ ...draft.value, name: draft.value.name.trim() })
		edit(flow.state.presets.find((p) => p.id === id))
	}
	flow.notify("Preset saved")
}

function back() {
	if (!dirty.value) {
		draft.value = null
		return
	}
	dialog.confirm({
		title: "Discard changes?",
		size: "lg",
		message: "Your edits to this preset have not been saved.",
		actions: [
			{ label: "Keep editing", variant: "outline" },
			{ label: "Discard", variant: "solid", theme: "red", onClick: () => (draft.value = null) },
		],
	})
}

function confirmDelete() {
	const { id, name } = draft.value
	dialog.confirm({
		title: "Delete preset?",
		size: "lg",
		message: `“${name}” will be removed.`,
		actions: [
			{ label: "Cancel", variant: "outline" },
			{
				label: "Delete",
				variant: "solid",
				theme: "red",
				onClick: () => {
					flow.deletePreset(id)
					draft.value = null
					flow.notify("Preset deleted")
				},
			},
		],
	})
}
</script>
