<script setup>
import { computed, defineAsyncComponent, ref, watch } from "vue";
import { Alert, FrappeUIProvider, setConfig } from "frappe-ui";
import { get, post } from "./api.js";
import WorkspaceGrid from "./WorkspaceGrid.vue";
import EmptyWorkspace from "./EmptyWorkspace.vue";

// read mode downloads no editor code
const WorkspaceEditor = defineAsyncComponent(() => import("./editor/WorkspaceEditor.vue"));
const ManageWorkspaces = defineAsyncComponent(() => import("./manage/ManageWorkspaces.vue"));

// Every workspace whose renderer is Frappe UI, drawn at its usual URL.

const props = defineProps({
	route: { type: Array, default: () => [] },
	query: { type: Object, default: () => ({}) },
});

const emit = defineEmits(["title", "actions"]);

const frappe = window.frappe;
const __ = window.__;

// frappe-ui's own requests, such as a doctype's meta, carry desk's session token
setConfig("requestHeaders", () => ({ "X-Frappe-CSRF-Token": frappe.csrf_token }));

const workspace = ref(null);
const not_found = ref(false);
const editing = ref(null);
const edit_count = ref(0);
const managing = ref(false);

// `/desk/<slug>` arrives as [name], `/desk/private/<title>` as ["private", name].
const target = computed(() =>
	props.route[0] === "private"
		? { name: props.route[1], private: true }
		: { name: props.route[0], private: false }
);

async function load() {
	const { name } = target.value;
	workspace.value = null;
	not_found.value = false;
	if (!name) return show_not_found();

	try {
		workspace.value = await get("frappe.desk.desktop.get_workspace", { name });
	} catch {
		return show_not_found();
	}
	correct_private_segment();
	emit("title", workspace.value.title);
	emit("actions", actions());

	// a new workspace, or one just switched here, opens in the editor
	if (frappe.ui.open_workspace_editor === workspace.value.name) {
		frappe.ui.open_workspace_editor = null;
		if (workspace.value.can_edit) edit();
	}
}

function show_not_found() {
	not_found.value = true;
	emit("title", __("Not found"));
	emit("actions", []);
}

// A public page is spelled /desk/<slug> and a private one /desk/private/<title>.
function correct_private_segment() {
	const page = workspace.value;
	if (page.public !== target.value.private) return;

	const slug = frappe.router.slug;
	const stored = frappe.boot.workspaces.pages.find((p) => p.name === page.name);
	const path = page.public
		? `/desk/${slug(page.name)}`
		: `/desk/private/${slug(stored?.title || page.title)}`;
	history.replaceState(history.state, "", path + window.location.search);
}

function actions() {
	const list = [];
	if (workspace.value.can_edit) list.push({ label: __("Edit"), onClick: () => edit() });
	list.push({ label: __("New Workspace"), onClick: () => frappe.ui.new_workspace_dialog() });
	if (workspace.value.can_edit) {
		list.push({ label: __("Manage"), onClick: () => (managing.value = true) });
	}
	if (workspace.value.is_layout_customized && workspace.value.can_edit) {
		list.push({ label: __("Reset to Standard"), onClick: reset });
	}
	return list;
}

// The editor opens on the default layout, whichever layout the reader was shown.
async function edit(variant) {
	editing.value = await get("frappe.desk.desktop.get_workspace", {
		name: workspace.value.name,
		variant: variant || "<default>",
	});
	edit_count.value++;
	const title = editing.value.public
		? __("Editing {0}", [editing.value.title])
		: __("Private / Editing {0}", [editing.value.title]);
	emit("title", title);
}

function stop_editing() {
	editing.value = null;
	load();
}

function reset() {
	const message = __(
		"Reset <b>{0}</b> to the standard, app-shipped version? This removes all site customizations.",
		[frappe.utils.escape_html(workspace.value.title)]
	);
	frappe.confirm(message, async () => {
		await post(
			"frappe.desk.doctype.custom_workspace.custom_workspace.reset_workspace_customization",
			{ workspace: workspace.value.name }
		);
		frappe.show_alert({ message: __("Workspace reset to standard"), indicator: "green" });
		load();
	});
}

watch(
	() => target.value.name + target.value.private,
	() => {
		editing.value = null;
		load();
	},
	{ immediate: true }
);
</script>

<template>
	<FrappeUIProvider>
		<ManageWorkspaces
			v-if="managing"
			:module="frappe.boot.workspaces.pages.find((p) => p.name === workspace?.name)?.module"
			@close="managing = false"
		/>
		<WorkspaceEditor
			v-if="editing"
			:key="edit_count"
			:workspace="editing"
			@saved="edit"
			@switch="edit"
			@done="stop_editing"
			@actions="(list) => emit('actions', list)"
		/>
		<div v-else class="mx-auto h-full max-w-4xl overflow-y-auto px-4 pt-4 pb-10">
			<div
				v-if="not_found"
				class="flex flex-col items-center gap-2 py-24 text-center text-ink-gray-5"
			>
				<span class="lucide-file-question size-6" aria-hidden="true" />
				<p class="text-base">
					{{ __("This workspace does not exist, or you cannot open it.") }}
				</p>
			</div>
			<template v-else-if="workspace">
				<Alert
					v-if="workspace.is_hidden && workspace.can_edit"
					class="mb-4"
					icon="lucide-eye-off"
					:title="
						__(
							'This workspace is hidden from other users. You can see it because you\'re a Workspace Manager.'
						)
					"
				/>
				<EmptyWorkspace
					v-if="!workspace.content.length"
					:can_edit="workspace.can_edit"
					@edit="edit()"
				/>
				<WorkspaceGrid v-else :content="workspace.content" :widgets="workspace.widgets" />
			</template>
		</div>
	</FrappeUIProvider>
</template>
