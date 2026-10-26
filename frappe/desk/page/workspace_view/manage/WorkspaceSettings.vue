<script setup>
import { computed, onMounted, ref } from "vue";
import { Button, FormControl, SettingsBody, SettingsHeader, TextInput } from "frappe-ui";
import { Link } from "@framework/ui";

// One workspace's title, module, icon and who can see it. A standard workspace keeps its
// title and module; its other changes are saved as the site's customization.
const props = defineProps({
	page: { type: Object, required: true },
	modules: { type: Array, required: true },
});

const emit = defineEmits(["back", "changed", "visit"]);

const frappe = window.frappe;
const __ = window.__;

const settings = ref(null);
const saving = ref(false);
const roles = ref([]);

onMounted(async () => {
	settings.value = await frappe.xcall(
		"frappe.desk.doctype.workspace.workspace.get_workspace_settings",
		{ name: props.page.name }
	);
	roles.value = [...settings.value.roles];
});

const ACCESS = {
	private: __("Only to you"),
	group: __("To a group of users"),
	public: __("To everyone"),
};

// A standard workspace is always shared; only a Workspace Manager can share a custom one.
const access_options = computed(() => {
	let keys = ["private"];
	if (settings.value.standard) keys = ["group", "public"];
	else if (frappe.boot.workspaces.has_access) keys = ["private", "group", "public"];
	return keys.map((value) => ({ label: ACCESS[value], value }));
});

const module_options = computed(() => frappe.ui.workspace_module_options(props.modules));

const can_visit = computed(() => props.page.public || props.page.for_user === frappe.session.user);

async function save() {
	saving.value = true;
	try {
		const s = settings.value;
		const message = await frappe.xcall(
			"frappe.desk.doctype.workspace.workspace.update_workspace_settings",
			{
				name: s.name,
				title: s.title,
				icon: s.icon,
				access: s.access,
				roles: s.access === "group" ? roles.value.filter(Boolean) : [],
				module: s.module,
			}
		);
		frappe.show_alert({ message: __("Workspace updated"), indicator: "green" });
		emit("changed", message, s.module);
	} finally {
		saving.value = false;
	}
}

function remove() {
	frappe.confirm(
		__("Delete the <b>{0}</b> workspace? This cannot be undone.", [
			frappe.utils.escape_html(__(props.page.title)),
		]),
		async () => {
			const message = await frappe.xcall(
				"frappe.desk.doctype.workspace.workspace.delete_page",
				{ name: props.page.name }
			);
			frappe.show_alert({
				message: __("Workspace {0} deleted", [__(props.page.title)]),
				indicator: "green",
			});
			emit("changed", message, props.page.module);
		}
	);
}

function visit() {
	emit("visit");
	frappe.set_route(frappe.ui.workspace_route(props.page));
}
</script>

<template>
	<SettingsHeader>
		<div class="flex flex-col gap-1">
			<div class="flex items-center justify-between gap-3">
				<div class="flex min-w-0 items-center gap-1">
					<Button
						variant="ghost"
						icon="lucide-chevron-left"
						:label="__('Back')"
						@click="emit('back')"
					/>
					<h2 class="truncate text-lg font-semibold text-ink-gray-8">
						{{ __(page.title) }}
					</h2>
				</div>
				<div class="flex shrink-0 items-center gap-2">
					<Button
						v-if="can_visit"
						icon-left="lucide-arrow-up-right"
						:label="__('Visit')"
						@click="visit"
					/>
					<Button
						v-if="settings && !settings.standard"
						theme="red"
						:label="__('Delete')"
						@click="remove"
					/>
					<Button variant="solid" :label="__('Save')" :loading="saving" @click="save" />
				</div>
			</div>
			<p class="text-base text-ink-gray-6">
				{{
					settings?.standard
						? __(
								"Shipped by its app; changes here are saved as this site's customization."
						  )
						: __("Who can see this workspace and how it appears.")
				}}
			</p>
		</div>
	</SettingsHeader>
	<SettingsBody>
		<div v-if="settings" class="flex flex-col gap-4 pt-2">
			<FormControl
				v-model="settings.title"
				type="text"
				:label="__('Title')"
				:disabled="settings.standard"
			/>
			<FormControl
				v-model="settings.module"
				type="select"
				:label="__('Module')"
				:options="module_options"
				:disabled="settings.standard"
				:description="__('Which module\'s sidebar this workspace appears in')"
			/>
			<TextInput
				v-model="settings.icon"
				:label="__('Icon')"
				:placeholder="__('Icon name')"
			/>
			<FormControl
				v-model="settings.access"
				type="select"
				:label="__('Access')"
				:options="access_options"
				:description="__('Who can see this workspace')"
			/>
			<div v-if="settings.access === 'group'" class="flex flex-col gap-2">
				<span class="text-sm text-ink-gray-5">
					{{ __("Users with any of these roles can see this workspace") }}
				</span>
				<div v-for="(role, index) in roles" :key="index" class="flex items-center gap-2">
					<Link v-model="roles[index]" class="flex-1" doctype="Role" />
					<Button
						variant="ghost"
						icon="lucide-x"
						:label="__('Remove role')"
						@click="roles.splice(index, 1)"
					/>
				</div>
				<Button
					class="self-start"
					icon-left="lucide-plus"
					:label="__('Add role')"
					@click="roles.push('')"
				/>
			</div>
		</div>
	</SettingsBody>
</template>
