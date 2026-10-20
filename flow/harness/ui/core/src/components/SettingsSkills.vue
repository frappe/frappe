<template>
	<!-- editor: a column that gives the textarea the dialog's height -->
	<div
		v-if="editing"
		class="flex min-h-0 flex-1 flex-col px-4 pb-6 pt-3 sm:px-8 md:pt-8"
		@keydown.meta.s.prevent="save"
		@keydown.ctrl.s.prevent="save"
	>
		<div class="flex items-center gap-2">
			<button v-if="!headerBack" class="flow-icon-btn -my-1 -ml-1.5" title="Back to skills" @click="back">
				<FeatherIcon name="arrow-left" class="h-4 w-4" />
			</button>
			<h2 class="text-base font-semibold text-ink-gray-9">{{ editing.isNew ? "New skill" : editing.name }}</h2>
			<Badge v-if="!editing.isNew" :label="SCOPE_LABELS[editing.scope]" variant="subtle" theme="gray" />
		</div>
		<template v-if="editing.isNew">
			<TextInput v-model="editing.name" class="mt-6" label="Name" placeholder="review-changes" autofocus />
			<p class="mt-1.5 text-2xs" :class="editing.name && !validName ? 'text-ink-red-6' : 'text-ink-gray-5'">
				Lowercase letters, digits, and single hyphens.
			</p>
			<Select v-model="editing.scope" class="mt-6 w-56" label="Where" :options="scopeOptions" />
			<p class="mt-1.5 text-2xs text-ink-gray-5">Saved as {{ shortPath(editing) }}</p>
		</template>
		<p v-else class="mt-2 text-xs leading-5 text-ink-gray-6" :title="editing.path">{{ shortPath(editing) }}</p>

		<textarea
			v-model="editing.content"
			class="mt-6 min-h-0 flex-1 resize-none rounded-5 border border-outline-gray-2 bg-surface-base p-3 font-mono text-2xs leading-relaxed text-ink-gray-9 outline-none focus:border-outline-gray-4 focus:ring-0"
			spellcheck="false"
		/>
		<p v-if="editing.error" class="mt-2 flex items-center gap-1.5 text-xs text-ink-red-6">
			<FeatherIcon name="alert-circle" class="h-3.5 w-3.5 flex-none" />
			{{ editing.error }}
		</p>

		<div class="mt-4 flex items-center justify-end gap-3">
			<span v-if="dirty" class="text-xs text-ink-gray-5">Unsaved changes</span>
			<Button v-if="!editing.isNew" label="Delete" variant="ghost" theme="red" :disabled="saving" @click="confirmDelete" />
			<Button variant="solid" label="Save" :disabled="!canSave" @click="save" />
		</div>
	</div>

	<!-- list -->
	<div v-else class="min-h-0 flex-1 overflow-y-auto px-4 pb-10 pt-3 sm:px-8 md:pt-8">
		<div class="flex items-start justify-between gap-4">
			<div>
				<h2 class="text-base font-semibold text-ink-gray-9">Skills</h2>
				<p class="mt-1 text-xs leading-5 text-ink-gray-6">Reusable instructions the agent can load.</p>
			</div>
			<Button v-if="!disabled && !layout.narrow" variant="solid" label="New skill" :disabled="!roots.global" @click="startNew" />
		</div>

		<div v-if="disabled" class="mt-6 rounded-5 border border-outline-gray-2 bg-surface-gray-1 px-4 py-3 text-xs text-ink-gray-7">
			Skill management is turned off by this daemon's policy.
		</div>

		<template v-else>
			<section v-for="scope in scopes" :key="scope.id" class="mt-8">
				<div class="flex items-center justify-between gap-4">
					<div class="text-sm font-medium text-ink-gray-9">{{ scope.title }}</div>
					<Select
						v-if="scope.id === 'project' && projects.length"
						:model-value="projectCwd ?? ''"
						:options="projectOptions"
						@update:model-value="selectedProject = $event"
					/>
					<span v-else class="truncate text-xs text-ink-gray-5" :title="scope.root">{{ scope.hint }}</span>
				</div>
				<div v-if="scope.rows.length" class="mt-3 max-h-80 divide-y divide-outline-gray-1 overflow-y-auto rounded-6 border border-outline-gray-2">
					<button
						v-for="row in scope.rows"
						:key="row.path"
						class="flex w-full items-center gap-4 px-3.5 py-3 text-left first:rounded-t-6 last:rounded-b-6 hover:bg-surface-gray-1"
						@click="open(row)"
					>
						<div class="min-w-0 flex-1">
							<div class="text-sm font-medium text-ink-gray-9">{{ row.name }}</div>
							<p v-if="row.error" class="mt-1 flex items-center gap-1.5 truncate text-xs text-ink-red-6">
								<FeatherIcon name="alert-circle" class="h-3.5 w-3.5 flex-none" />
								{{ row.error }}
							</p>
							<p v-else class="mt-1 truncate text-xs text-ink-gray-6">{{ row.description }}</p>
						</div>
						<FeatherIcon name="chevron-right" class="h-4 w-4 flex-none text-ink-gray-4" />
					</button>
				</div>
				<p v-else-if="!loading" class="mt-3 text-xs text-ink-gray-5">{{ scope.empty }}</p>
				<LoadingState v-else class="mt-3 text-xs text-ink-gray-5" />
				<p v-if="scope.cut" class="mt-2 text-xs text-ink-gray-5">Not every skill is shown: this folder has too many entries.</p>
			</section>
			<!-- a narrow frame has no room beside the heading: the button ends the page -->
			<Button v-if="layout.narrow" class="mt-8" variant="solid" label="New skill" :disabled="!roots.global" @click="startNew" />
		</template>
	</div>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import { Badge } from "frappe-ui/src/components/Badge"
import { Button } from "frappe-ui/src/components/Button"
import { Select } from "frappe-ui/src/components/Select"
import { TextInput } from "frappe-ui/src/components/TextInput"
import { dialog } from "frappe-ui/src/utils/dialog"
import FeatherIcon from "./FeatherIcon.vue"
import LoadingState from "./LoadingState.vue"

import { layout } from "../layout.js"
import { useSettingsBack } from "../settingsBack.js"

const flow = inject("flow")

const SCOPE_LABELS = { global: "Global", project: "Project" }
const NAME_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/

const rows = ref([])
const roots = ref({})
const truncated = ref([]) // scopes whose folder had more entries than the daemon scans
const loading = ref(false)
const disabled = ref(false)
const editing = ref(null) // { path, name, scope, content, saved, error, isNew }
const headerBack = useSettingsBack(() => !!editing.value, back)
const saving = ref(false)

const folderName = (cwd) => cwd.replace(/[\\/]+$/, "").split(/[\\/]/).filter(Boolean).pop() ?? cwd

// "." is the daemon-side default, not a project
const currentCwd = computed(() => {
	const raw = flow.state.sessionId ? flow.state.session?.config?.cwd : flow.state.prefs.cwd
	return raw && raw !== "." ? raw : null
})
// every folder a chat has run in, current one first; the filter picks among them
const projects = computed(() => {
	const cwds = [currentCwd.value, ...flow.state.sessions.map((s) => s.cwd?.trim())]
	return [...new Set(cwds.filter((cwd) => cwd && cwd !== "."))]
})
const projectOptions = computed(() => projects.value.map((cwd) => ({ value: cwd, label: folderName(cwd) })))
const selectedProject = ref(null)
const projectCwd = computed(() =>
	projects.value.includes(selectedProject.value) ? selectedProject.value : (projects.value[0] ?? null),
)
const projectName = computed(() => (projectCwd.value ? folderName(projectCwd.value) : ""))

const scopes = computed(() => [
	{
		id: "global",
		title: "Global",
		hint: "~/.agents/skills",
		root: roots.value.global,
		rows: rows.value.filter((r) => r.scope === "global"),
		cut: truncated.value.includes("global"),
		empty: "No global skills yet.",
	},
	{
		id: "project",
		title: "Project",
		hint: "",
		root: roots.value.project,
		rows: rows.value.filter((r) => r.scope === "project"),
		cut: truncated.value.includes("project"),
		empty: projectCwd.value ? `No skills in ${projectName.value} yet.` : "Start a chat in a folder to see its skills.",
	},
])
const scopeOptions = computed(() => [
	{ value: "global", label: "Global" },
	...(projectCwd.value ? [{ value: "project", label: `Project · ${projectName.value}` }] : []),
])
const validName = computed(() => {
	const name = editing.value?.name ?? ""
	return NAME_RE.test(name) && name.length <= 64
})
const dirty = computed(() => !!editing.value && editing.value.content !== editing.value.saved)
const canSave = computed(() => dirty.value && !saving.value && (!editing.value.isNew || validName.value))

// the root portion is noise: show where the file sits under its root
function shortPath(row) {
	const root = row.scope === "global" ? "~/.agents/skills" : `${projectName.value}/.agents/skills`
	return `${root}/${row.name || "<name>"}/SKILL.md`
}

// a new skill's name field drives the frontmatter `name:` line, which must match its folder
watch(
	() => editing.value?.name,
	(name, previous) => {
		const draft = editing.value
		if (!draft?.isNew || name === previous) return
		draft.content = draft.content.replace(/^name: .*$/m, `name: ${name}`)
	},
)

async function load() {
	loading.value = true
	try {
		const data = await flow.client.skillFiles(projectCwd.value)
		rows.value = data.skills
		roots.value = data.roots
		truncated.value = data.truncated ?? []
		disabled.value = false
	} catch (error) {
		if (error.status === 403) disabled.value = true
		else flow.notify(error.message, "error")
	} finally {
		loading.value = false
	}
}
watch(
	() => [flow.state.settingsOpen, projectCwd.value],
	([open], previous) => {
		if (!open) return
		if (!previous?.[0] && !editing.value) selectedProject.value = currentCwd.value
		if (editing.value?.isNew && editing.value.scope === "project" && !projectCwd.value) editing.value.scope = "global"
		load()
	},
	{ immediate: true },
)

async function open(row) {
	try {
		const data = await flow.client.readSkill(row.path, projectCwd.value)
		editing.value = { ...row, content: data.content, saved: data.content, isNew: false }
	} catch (error) {
		flow.notify(error.message, "error")
	}
}

function startNew() {
	editing.value = {
		path: null,
		name: "",
		scope: "global",
		content: "---\nname: \ndescription: When the agent should use this skill\n---\n\n# Steps\n\n1. \n",
		saved: null,
		error: null,
		isNew: true,
	}
}

async function save() {
	if (!canSave.value) return
	const draft = editing.value
	if (draft.isNew) draft.path = `${roots.value[draft.scope]}/${draft.name}/SKILL.md`
	saving.value = true
	try {
		// the daemon's write replaces whatever is there
		if (draft.isNew && (await skillExists(draft))) {
			draft.error = `A ${draft.scope} skill named “${draft.name}” already exists.`
			return
		}
		await flow.client.writeSkill(draft.path, draft.content, projectCwd.value)
		draft.saved = draft.content
		draft.error = null
		draft.isNew = false
		flow.notify("Skill saved")
		load()
		// the open session can invoke this now, so refresh its command list
		flow.loadSkills?.({ force: true })
	} catch (error) {
		// the daemon refuses invalid content and says why; the draft stays unsaved
		draft.error = error.message
		if (error.status !== 400) flow.notify(error.message, "error")
	} finally {
		saving.value = false
	}
}

// the list may be cut off, or older than a skill made since, so the daemon is asked too
async function skillExists({ scope, name, path }) {
	if (rows.value.some((row) => row.scope === scope && row.name === name)) return true
	try {
		await flow.client.readSkill(path, projectCwd.value)
		return true
	} catch (error) {
		if (error.status === 404) return false
		throw error
	}
}

function back() {
	if (!dirty.value) {
		editing.value = null
		return
	}
	dialog.confirm({
		title: "Discard changes?",
		size: "lg",
		message: "Your edits to this skill have not been saved.",
		actions: [
			{ label: "Keep editing", variant: "outline" },
			{ label: "Discard", variant: "solid", theme: "red", onClick: () => (editing.value = null) },
		],
	})
}

function confirmDelete() {
	const { path, name } = editing.value
	dialog.confirm({
		title: "Delete skill?",
		size: "lg",
		message: `“${name}” will be removed from disk.`,
		actions: [
			{ label: "Cancel", variant: "outline" },
			{
				label: "Delete",
				variant: "solid",
				theme: "red",
				onClick: async () => {
					try {
						await flow.client.deleteSkill(path, projectCwd.value)
						editing.value = null
						flow.notify("Skill deleted")
						load()
						flow.loadSkills?.({ force: true })
					} catch (error) {
						flow.notify(error.message, "error")
					}
				},
			},
		],
	})
}
</script>
