<script setup>
import { computed, defineAsyncComponent, nextTick, ref, shallowRef, watch } from "vue";
import { Alert, FrappeUIProvider, setConfig } from "frappe-ui";
import { get, post } from "./api.js";
import WorkspaceGrid from "./WorkspaceGrid.vue";
import EmptyWorkspace from "./EmptyWorkspace.vue";
import { block_rects, glide } from "./grid.js";

// read mode downloads no editor code
const WorkspaceEditor = shallowRef(null);
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
// the pane on show, kept while a save mounts its successor so the grid never falls back to read
const editor = shallowRef(null);
const blocks_root = ref(null);

// One grid draws the page read and edited, so its tiles keep their data across the switch.
const canvas = computed(() => {
	if (editing.value && editor.value) {
		const { blocks, widgets, previewing, selected_id, variant } = editor.value;
		return {
			content: blocks,
			widgets,
			editing: !previewing,
			previewing,
			selected_id,
			variant,
		};
	}
	const page = workspace.value;
	return page && { content: page.content, widgets: page.widgets, hidden: page.is_hidden };
});
const pane_open = computed(() => !!canvas.value?.editing);

// The pane slides in from the edge as the blocks glide over to make room, and back out the same way.
const DRAWER = "cubic-bezier(0.32, 0.72, 0, 1)";
watch(
	pane_open,
	async (open) => {
		const before = block_rects(blocks_root.value);
		await nextTick();
		glide(blocks_root.value, before, { duration: 300, easing: DRAWER });
	},
	{ flush: "pre" }
);

// `/desk/<slug>` arrives as [name], `/desk/private/<title>` as ["private", name].
const target = computed(() =>
	props.route[0] === "private"
		? { name: props.route[1], private: true }
		: { name: props.route[0], private: false }
);

async function load() {
	const { name } = target.value;
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
	const [page, module] = await Promise.all([
		get("frappe.desk.desktop.get_workspace", {
			name: workspace.value.name,
			variant: variant || "<default>",
		}),
		import("./editor/WorkspaceEditor.vue"),
	]);
	WorkspaceEditor.value = module.default;
	editing.value = page;
	edit_count.value++;
	const title = editing.value.public
		? __("Editing {0}", [editing.value.title])
		: __("Private / Editing {0}", [editing.value.title]);
	emit("title", title);
}

async function stop_editing() {
	await load();
	editing.value = null;
	editor.value = null;
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
		editor.value = null;
		workspace.value = null;
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
		<div class="relative h-full overflow-hidden">
			<div
				class="h-full overflow-y-auto px-4 pt-4 pb-10"
				:class="{ 'mr-[22rem]': pane_open }"
			>
				<div ref="blocks_root" class="mx-auto max-w-4xl">
					<div
						v-if="not_found"
						class="flex flex-col items-center gap-2 py-24 text-center text-ink-gray-5"
					>
						<span class="lucide-file-question size-6" aria-hidden="true" />
						<p class="text-base">
							{{ __("This workspace does not exist, or you cannot open it.") }}
						</p>
					</div>
					<template v-else-if="canvas">
						<Transition
							enter-active-class="transition duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:transition-opacity"
							enter-from-class="-translate-y-1 opacity-0 motion-reduce:translate-y-0"
							leave-active-class="transition duration-150 ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:transition-opacity"
							leave-to-class="-translate-y-1 opacity-0 motion-reduce:translate-y-0"
						>
							<Alert
								v-if="canvas.previewing"
								class="mb-4"
								icon="lucide-eye"
								:title="
									canvas.variant
										? __('Previewing the {0} layout with your data.', [
												__(canvas.variant),
										  ])
										: __('Previewing the default layout with your data.')
								"
							/>
						</Transition>
						<Alert
							v-if="canvas.hidden && workspace.can_edit"
							class="mb-4"
							icon="lucide-eye-off"
							:title="
								__(
									'This workspace is hidden from other users. You can see it because you\'re a Workspace Manager.'
								)
							"
						/>
						<EmptyWorkspace
							v-if="!canvas.content.length && !canvas.previewing"
							:editing="canvas.editing"
							:can_edit="workspace.can_edit"
							@edit="edit()"
							@add-text="editor.add_text()"
						/>
						<WorkspaceGrid
							v-else
							:content="canvas.content"
							:widgets="canvas.widgets"
							:editing="canvas.editing"
							:selected="canvas.selected_id"
							@select="(block) => (editor.selected_id = block.id)"
							@move="(id, target) => editor.on_move(id, target)"
						/>
					</template>
				</div>
			</div>
			<Transition
				enter-active-class="transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] motion-reduce:transition-opacity"
				enter-from-class="translate-x-[calc(100%+1rem)] opacity-0 motion-reduce:translate-x-0"
				leave-active-class="transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] motion-reduce:transition-opacity"
				leave-to-class="translate-x-[calc(100%+1rem)] opacity-0 motion-reduce:translate-x-0"
			>
				<div
					v-if="editing"
					v-show="pane_open"
					class="absolute inset-y-0 right-0 flex w-[22rem] flex-col"
				>
					<component
						:is="WorkspaceEditor"
						:ref="(pane) => pane && (editor = pane)"
						:key="edit_count"
						:workspace="editing"
						@saved="edit"
						@switch="edit"
						@done="stop_editing"
						@actions="(list) => emit('actions', list)"
					/>
				</div>
			</Transition>
		</div>
	</FrappeUIProvider>
</template>
