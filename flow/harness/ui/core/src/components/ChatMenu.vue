<template>
	<!-- open and update:open, when given, pass through to the Dropdown -->
	<Dropdown :align="align" :options="options">
		<template #trigger><slot /></template>
	</Dropdown>
</template>

<script setup>
import { computed, inject } from "vue"
import Dropdown from "frappe-ui/src/components/Dropdown/Dropdown.vue"

import { dialog } from "frappe-ui/src/utils/dialog"

import { afterMenu } from "../menu.js"

// A chat's menu, for its sidebar row and the header: the host's own items, then Rename and Delete
// once there is a chat to rename. Rename asks the row or header it came from to edit the name in place
const props = defineProps({
	sessionId: { type: String, default: null },
	title: { type: String, required: true },
	actions: { type: Array, default: () => [] },
	align: { type: String, default: "end" },
})
const emit = defineEmits(["rename"])
const flow = inject("flow")

const own = computed(() =>
	props.sessionId
		? [
				{ label: "Rename", icon: "lucide-pen", onClick: () => emit("rename") },
				{ label: "Delete", icon: "lucide-trash-2", theme: "red", onClick: confirmDelete },
			]
		: [],
)

const options = computed(() =>
	[...props.actions, ...own.value].map((item) => ({ ...item, onClick: afterMenu((...args) => item.onClick?.(...args)) })),
)

// the dialog keeps the chat it was opened for, even if another one opens meanwhile.
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
