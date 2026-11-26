<template>
	<div class="flex flex-col divide-y divide-outline-gray-1 px-4">
		<section v-for="(rows, index) in groups" :key="index" class="flex flex-col gap-1 py-3">
			<div
				v-for="row in rows"
				:key="row.title"
				class="-mx-2 rounded-4 p-2 flex flex-col gap-1"
				:class="{ 'cursor-pointer hover:bg-surface-gray-1': row.onClick }"
				:role="row.onClick ? 'button' : undefined"
				:tabindex="row.onClick ? 0 : undefined"
				@click="row.onClick?.()"
				@keydown.enter="row.onClick?.()"
				@keydown.space.prevent="row.onClick?.()"
			>
				<span class="flex items-center gap-2">
					<span
						class="h-4 w-4 shrink-0"
						:class="[row.icon, row.onClick ? 'text-ink-gray-7' : 'text-ink-gray-5']"
					/>
					<span class="flex-1 text-base" :class="row.onClick ? 'text-ink-gray-8' : 'text-ink-gray-6'">
						{{ row.title }}
					</span>
					<Badge v-if="row.badge" variant="outline" theme="gray" :label="row.badge" />
					<span v-else class="h-3.5 w-3.5 shrink-0 text-ink-gray-5" :class="row.action" />
				</span>
				<span class="pl-6 text-sm leading-5 text-ink-gray-5">{{ row.caption }}</span>
			</div>
		</section>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Badge, createResource } from "frappe-ui"

import useStudioStore from "@/stores/studioStore"
import { copyToClipboard } from "@/utils/helpers"

type Row = {
	icon: string
	title: string
	caption: string
	action?: string
	badge?: string
	onClick?: () => void
}

const store = useStudioStore()
const canUseFlow = createResource({ url: "frappe.studio.api.can_use_flow", auto: true })

const flowRow = computed<Row>(() =>
	canUseFlow.data
		? {
				icon: "lucide-message-square",
				title: "Flow",
				caption: "Chat on this site",
				action: "lucide-arrow-up-right",
				onClick: openFlow,
			}
		: {
				icon: "lucide-message-square",
				title: "Flow",
				caption: "Chat on this site. Needs the Flow User role. Ask your admin for access.",
				action: "lucide-lock",
			},
)

const groups = computed<Row[][]>(() => [
	[
		flowRow.value,
		{
			icon: "lucide-square-terminal",
			title: "Your own agent",
			caption: "Copy a prompt for Claude Code, Codex and others",
			action: "lucide-copy",
			onClick: copyPrompt,
		},
	],
	[
		{
			icon: "lucide-sparkle",
			title: "In-editor agent",
			caption: "Edit with AI right on the canvas",
			badge: "Coming soon",
		},
	],
])

// the docked chat where Flow's launcher is on the page, else Flow's own page
function openFlow() {
	const launcher = (window as any).flow
	launcher ? launcher.toggle() : window.open("/flow", "_blank")
}

function copyPrompt() {
	const site = import.meta.env.DEV ? window.site_url : window.location.origin
	const app = store.activeApp
	const skill =
		"- Install the `studio-app-building` skill from `frappe/frappe` with `npx skills` and read its SKILL.md."
	const preview = `- When you finish a task, list the pages you changed with their preview links under \`${site}/dev/${app?.route}\`, so I can check them.`

	const lines = app?.is_standard
		? [
				`Work with me on the Studio app \`${app.name}\` on \`${site}\`. ` +
					`It is a standard app: its files are in the \`studio\` folder of the Frappe app \`${app.frappe_app}\` on this bench.`,
				"",
				skill,
				`- Edit the app's files. Keep \`bench --site ${window.site_name} watch-studio\` running so the site imports your changes.`,
				preview,
			]
		: [
				`Work with me on the Studio app \`${app?.name}\` on \`${site}\`.`,
				"",
				skill,
				"- Talk to the site with frappectl. Install it with `uv tool install frappectl` and read `frappectl guide`.",
				`- If frappectl is not logged in to this site, stop and ask me to run \`frappectl auth login ${site} --writable\`. ` +
					"Never create or change users, passwords or API keys yourself.",
				preview,
			]
	copyToClipboard(lines.join("\n"))
}
</script>
