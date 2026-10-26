<script setup>
import { computed, ref, watch } from "vue";
import { FrappeUIProvider, setConfig } from "frappe-ui";
import { get, post } from "./api.js";
import WorkspaceGrid from "./WorkspaceGrid.vue";

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
	const list = [{ label: __("New Workspace"), onClick: () => frappe.ui.new_workspace_dialog() }];
	if (workspace.value.can_edit) {
		list.push({ label: __("Manage"), onClick: () => frappe.set_route("List", "Workspace") });
	}
	if (workspace.value.is_layout_customized && workspace.value.can_edit) {
		list.push({ label: __("Reset to Standard"), onClick: reset });
	}
	return list;
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

watch(() => target.value.name + target.value.private, load, { immediate: true });
</script>

<template>
	<FrappeUIProvider>
		<div class="mx-auto h-full max-w-4xl overflow-y-auto px-4 pt-4 pb-10">
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
				<div
					v-if="workspace.is_hidden && workspace.can_edit"
					class="mb-4 rounded-6 bg-surface-gray-2 px-3 py-2 text-base text-ink-gray-6"
				>
					{{
						__(
							"This workspace is hidden from other users. You can see it because you're a Workspace Manager."
						)
					}}
				</div>
				<WorkspaceGrid :content="workspace.content" :widgets="workspace.widgets" />
			</template>
		</div>
	</FrappeUIProvider>
</template>
