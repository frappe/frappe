<template>
	<!-- open and update:open, when given, pass through to the Dropdown -->
	<Dropdown align="end" :options="[...actions, ...own]">
		<template #trigger><slot /></template>
	</Dropdown>
</template>

<script setup>
import { inject } from "vue"
import Dropdown from "frappe-ui/src/components/Dropdown/Dropdown.vue"

import { dialog } from "frappe-ui/src/utils/dialog"

// A chat's menu, for its sidebar row and the header: the host's own items, then Rename and Delete
const props = defineProps({
	sessionId: { type: String, required: true },
	title: { type: String, required: true },
	actions: { type: Array, default: () => [] },
})
const flow = inject("flow")

const own = [
	{ label: "Rename", icon: "lucide-pen", onClick: promptRename },
	{ label: "Delete", icon: "lucide-trash-2", theme: "red", onClick: confirmDelete },
]

// each dialog keeps the chat it was opened for, even if another one opens meanwhile
function promptRename() {
	const sid = props.sessionId
	dialog.prompt({
		title: "Rename chat",
		size: "lg",
		fields: [{ name: "title", label: "Name", defaultValue: props.title, required: true }],
		confirmLabel: "Rename",
		// fire-and-forget (outcome lands as a toast): returning the promise would
		// flash the button's loading state for ~20ms and jolt the action row
		onConfirm: ({ values }) => {
			void flow.renameSession(sid, values.title.trim())
		},
	})
}

// dialog.confirm, not dialog.danger: danger's red theme injects a header
// icon; the destructive styling lives on the action button instead
function confirmDelete() {
	const sid = props.sessionId
	dialog.confirm({
		title: "Delete chat?",
		size: "lg",
		message: `“${props.title}” and its full history will be permanently removed.`,
		actions: [
			{ label: "Cancel", variant: "outline" },
			{
				label: "Delete",
				variant: "solid",
				theme: "red",
				onClick: () => {
					void flow.deleteSession(sid)
				},
			},
		],
	})
}
</script>
