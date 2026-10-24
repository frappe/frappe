<template>
	<PageHeader
		:icon="info.icon"
		:title="name ?? `New ${spec.singular}`"
		:list="list"
		@back="toList(false)"
	>
		<template #actions>
			<span v-if="doc && !canWrite" class="text-xs text-ink-gray-5">View only</span>
			<span v-if="canWrite && dirty" class="text-xs text-ink-gray-5 max-sm:hidden"
				>Unsaved changes</span
			>
			<Button
				v-for="action in actions"
				:key="action.label"
				:label="action.label"
				:loading="running === action.label"
				:disabled="dirty"
				:title="dirty ? 'Save first' : ''"
				@click="runAction(action)"
			/>
			<!-- a phone's bar keeps room for the title: the button keeps its icon -->
			<Button
				v-if="canChat && layout.narrow"
				icon="lucide-message-square"
				title="Start chat"
				@click="chat"
			/>
			<Button
				v-else-if="canChat"
				icon-left="lucide-message-square"
				label="Start chat"
				@click="chat"
			/>
			<Dropdown v-if="canDelete" align="end" :options="menu">
				<template #trigger>
					<button class="flow-icon-btn" title="More">
						<FeatherIcon name="more-horizontal" class="h-4 w-4" />
					</button>
				</template>
			</Dropdown>
			<Button
				v-if="canWrite && doc"
				variant="solid"
				:label="isNew ? 'Create' : 'Save'"
				:loading="saving"
				:disabled="!dirty"
				@click="save"
			/>
		</template>
	</PageHeader>
	<div class="min-h-0 flex-1 overflow-y-auto">
		<form
			v-if="doc"
			ref="form"
			class="mx-auto w-full max-w-[800px] px-4 pb-16 pt-6 sm:px-6"
			@submit.prevent="save"
		>
			<p
				v-if="doc.is_system_generated && canWrite"
				class="mb-5 rounded-5 bg-surface-gray-2 px-3 py-2 text-xs leading-5 text-ink-gray-7"
			>
				Comes with an app, so greyed-out fields can't be changed.
			</p>
			<!-- each section under its heading; two short fields share a line on a wide frame -->
			<section v-for="(group, i) in groups" :key="i">
				<h2
					v-if="group.title"
					class="mb-5 mt-10 border-t border-outline-gray-1 pt-8 text-lg font-semibold text-ink-gray-9"
				>
					{{ group.title }}
				</h2>
				<div class="grid grid-cols-1 gap-5 sm:grid-cols-2">
					<div
						v-for="field in group.fields"
						:key="field.name"
						class="min-w-0"
						:class="field.half ? '' : 'sm:col-span-2'"
					>
						<FieldControl
							v-if="canWrite"
							:field="field"
							:doc="doc"
							:disabled="isLocked(field)"
						/>
						<!-- one who may only read it sees its values, not disabled inputs -->
						<div v-else class="flex flex-col gap-1.5">
							<span class="text-xs text-ink-gray-5">{{ field.label }}</span>
							<span
								v-if="field.type === 'multilink' && doc[field.name]?.length"
								class="flex flex-wrap gap-1.5"
							>
								<span
									v-for="item in doc[field.name]"
									:key="item"
									class="rounded-4 bg-surface-gray-2 px-2 py-0.5 text-sm text-ink-gray-8"
									>{{ item }}</span
								>
							</span>
							<span
								v-else
								class="whitespace-pre-wrap break-words text-sm leading-6"
								:class="[
									shown(field) ? 'text-ink-gray-8' : 'text-ink-gray-4',
									field.type === 'code' && 'font-mono text-xs',
								]"
								>{{ shown(field) || "None" }}</span
							>
						</div>
					</div>
				</div>
			</section>
		</form>
		<p v-else-if="error" class="px-6 py-16 text-center text-sm text-ink-gray-5">{{ error }}</p>
		<LoadingState v-else class="justify-center py-16 text-xs text-ink-gray-5" />
	</div>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, watch } from "vue";
import { useRouter } from "vue-router";
import { Button, dialog, toast } from "frappe-ui";
import Dropdown from "frappe-ui/src/components/Dropdown/Dropdown.vue";
import FeatherIcon from "@flow/ui-core/components/FeatherIcon.vue";
import LoadingState from "@flow/ui-core/components/LoadingState.vue";
import { layout } from "@flow/ui-core/layout.js";

import FieldControl from "../settings/FieldControl.vue";
import { useRecord } from "../settings/records.js";
import PageHeader from "./PageHeader.vue";

// A record's page: its fields in the column, by section, its actions in the bar. Leaving it
// with edits unsaved asks first.
const props = defineProps({
	spec: { type: Object, required: true },
	info: { type: Object, required: true }, // the page's entry in PAGES
	name: { type: String, default: null }, // null for a new record
});
const flow = inject("flow");
const page = inject("flowPage");
const leavePage = inject("leavePage");
const router = useRouter();
// the list it was opened from, with its search and filters
const listPath = `/${props.spec.key}`;
const opener = router.options.history.state.back;
const list = {
	to: opener?.split("?")[0] === listPath ? opener : listPath,
	label: props.spec.label,
};

let leaving = false; // a deleted record's page goes without asking
const {
	doc,
	form,
	error,
	saving,
	running,
	isNew,
	canWrite,
	canDelete,
	dirty,
	visibleFields,
	actions,
	isLocked,
	save,
	remove,
	runAction,
} = useRecord(props, (event, saved) => {
	// a new or renamed record takes its old address's place
	if (event === "saved" && saved.name !== props.name)
		router.replace({ name: "records", params: { kind: props.spec.key, record: saved.name } });
	if (event === "deleted") {
		leaving = true;
		toList();
	}
});
// the bar has no room for a failure's reason: it pops up instead, unless the record never loaded
watch(error, (message) => message && doc.value && toast.error(message));

// the fields cut into sections where one starts its own; a reader's leave out the name, which the
// bar shows
const groups = computed(() =>
	visibleFields.value
		.filter((field) => canWrite.value || !field.rename)
		.reduce((groups, field) => {
			if (field.section || !groups.length) groups.push({ title: field.section, fields: [] });
			groups.at(-1).fields.push(field);
			return groups;
		}, [])
);

// a field's value as read: numbers with separators, an unset number its placeholder ("No limit")
function shown(field) {
	const value = doc.value[field.name];
	if (field.type === "check") return value ? "Yes" : "No";
	if (field.type === "int") return value ? value.toLocaleString() : field.placeholder ?? "0";
	return value == null ? "" : String(value);
}

const menu = computed(() => [
	{ label: "Delete", icon: "lucide-trash-2", theme: "red", onClick: remove },
]);

// an agent the user may chat with starts a new chat from its page, in place of the one waiting
// behind it, once the page lets go
const canChat = computed(
	() =>
		props.spec.doctype === "Flow Agent" &&
		page.state.boot.agents.some((agent) => agent.name === props.name)
);
async function chat() {
	if (!(await leavePage())) return;
	flow.startNewChat();
	page.state.agent = props.name;
}

// back to the list it came from, its filters and all; else to the list, in a deleted record's
// place (`replace`) so Back doesn't return to it
function toList(replace = true) {
	const back = router.options.history.state.back;
	if (back?.split("?")[0] === listPath) router.back();
	else if (replace) router.replace(listPath);
	else router.push(listPath);
}

function discard() {
	return new Promise((resolve) => {
		dialog.confirm({
			title: "Discard changes?",
			size: "lg",
			message: `Your changes to this ${props.spec.singular} are not saved.`,
			actions: [
				{ label: "Keep editing", variant: "outline", onClick: () => resolve(false) },
				{ label: "Discard", variant: "solid", theme: "red", onClick: () => resolve(true) },
			],
			onCancel: () => resolve(false),
		});
	});
}
const unguard = router.beforeEach(() => leaving || !dirty.value || discard());
function onUnload(event) {
	if (dirty.value) event.preventDefault();
}
window.addEventListener("beforeunload", onUnload);
onBeforeUnmount(() => {
	unguard();
	window.removeEventListener("beforeunload", onUnload);
});
</script>
