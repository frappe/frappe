<script setup>
import { computed, onMounted, ref, watch } from "vue";
import {
	Avatar,
	Badge,
	SettingsBody,
	SettingsContent,
	SettingsDialog,
	SettingsHeader,
	SettingsNavGroup,
	SettingsNavItem,
	SettingsPanel,
	SettingsSidebar,
	TextInput,
} from "frappe-ui";
import { List, ListCell, ListHeader, ListHeaderCellSort, ListRow, ListRows } from "frappe-ui/list";
import WorkspaceSettings from "./WorkspaceSettings.vue";

// Every workspace the user may manage, grouped by the module that decides where it appears.
const props = defineProps({
	module: { type: String, default: null },
});

const emit = defineEmits(["close"]);

const frappe = window.frappe;
const __ = window.__;
const NO_MODULE = "__no_module__";

const open = ref(true);
const tab = ref(null);
const search = ref("");
const pages = ref([]);
const modules = ref([]);
const editing = ref(null);

watch(open, (value) => !value && emit("close"));

async function load(module) {
	const [manageable, assignable] = await Promise.all([
		frappe.xcall("frappe.desk.doctype.workspace.workspace.get_manageable_workspaces"),
		frappe.ui.get_assignable_modules(),
	]);
	pages.value = manageable || [];
	modules.value = assignable || [];
	editing.value = null;
	tab.value = groups.value.some((g) => g.key === (module || NO_MODULE))
		? module || NO_MODULE
		: groups.value[0]?.key;
}

onMounted(() => load(props.module));

// One nav item per module that holds a match. Unreachable ones, with no module or one that
// does not exist, come first since they are the ones worth fixing.
const groups = computed(() => {
	const meta = Object.fromEntries(modules.value.map((m) => [m.module, m]));
	const query = search.value.trim().toLowerCase();
	const by_module = new Map();
	for (const page of pages.value) {
		if (query && !__(page.title).toLowerCase().includes(query)) continue;
		const key = page.module || NO_MODULE;
		if (!by_module.has(key)) by_module.set(key, []);
		by_module.get(key).push(page);
	}

	const rank = (key) => (key === NO_MODULE || !meta[key] ? 0 : 1);
	const label = (key) => (key === NO_MODULE ? __("No module") : __(meta[key]?.label || key));
	return [...by_module.keys()]
		.sort((a, b) => rank(a) - rank(b) || label(a).localeCompare(label(b)))
		.map((key) => ({
			key,
			label: label(key),
			module: meta[key],
			pages: by_module.get(key),
		}));
});

// a search that leaves the open module empty moves to the first one it found
watch(groups, (list) => {
	if (list.length && !list.some((g) => g.key === tab.value)) tab.value = list[0].key;
});
watch(tab, () => (editing.value = null));

function describe(group) {
	const count = group.pages.length;
	if (group.key === NO_MODULE) {
		return __("{0} workspace(s) with no module, so nothing navigates to them.", [count]);
	}
	if (!group.module) {
		return __("{0} workspace(s) naming the module {1}, which this site doesn't have.", [
			count,
			group.key,
		]);
	}
	if (group.module.app_title) {
		return __("{0} workspace(s) in this module, which {1} ships.", [
			count,
			__(group.module.app_title),
		]);
	}
	return __("{0} workspace(s) in this module, which this site owns.", [count]);
}

function access(page) {
	if (page.standard) return { label: __("Standard"), theme: "blue" };
	if (page.public) return { label: __("Everyone"), theme: "green" };
	return { label: page.for_user ? __("Private") : __("Shared"), theme: "gray" };
}

// Sorting is the list's own: by title, owner or access, toggled from the header.
const sort = ref({ field: "title", direction: "asc" });

function toggle_sort(field) {
	const same = sort.value.field === field;
	sort.value = { field, direction: same && sort.value.direction === "asc" ? "desc" : "asc" };
}

function direction_for(field) {
	return sort.value.field === field ? sort.value.direction : null;
}

function sort_icon(direction) {
	if (!direction) return "lucide-arrow-up-down";
	return direction === "asc" ? "lucide-arrow-up" : "lucide-arrow-down";
}

function sorted(list) {
	const { field, direction } = sort.value;
	const key = (page) =>
		field === "access"
			? access(page).label
			: field === "owner"
			? page.for_user || ""
			: __(page.title);
	const factor = direction === "desc" ? -1 : 1;
	return [...list].sort((a, b) => factor * key(a).localeCompare(key(b)));
}

function owner(page) {
	const info = frappe.user_info(page.for_user);
	return { name: info.fullname || page.for_user, image: info.image };
}

function changed(message, module) {
	frappe.ui.update_workspace_pages(message);
	load(module);
}
</script>

<template>
	<SettingsDialog v-model:open="open" v-model:tab="tab" :keyboard-shortcut="false">
		<template #title>{{ __("Manage Workspaces") }}</template>
		<SettingsSidebar>
			<h2 class="px-2 pt-1 text-lg font-semibold text-ink-gray-8">
				{{ __("Manage Workspaces") }}
			</h2>
			<TextInput v-model="search" :placeholder="__('Search workspaces')">
				<template #prefix>
					<span class="lucide-search size-4 text-ink-gray-4" aria-hidden="true" />
				</template>
			</TextInput>
			<SettingsNavGroup :label="__('Modules')">
				<SettingsNavItem v-for="group in groups" :key="group.key" :value="group.key">
					{{ group.label }}
					<template #suffix>
						<span class="text-sm text-ink-gray-5">{{ group.pages.length }}</span>
					</template>
				</SettingsNavItem>
			</SettingsNavGroup>
			<p v-if="!groups.length" class="px-2 text-base text-ink-gray-5">
				{{ __("No workspace matches.") }}
			</p>
		</SettingsSidebar>
		<SettingsContent>
			<SettingsPanel v-for="group in groups" :key="group.key" :value="group.key">
				<WorkspaceSettings
					v-if="editing"
					:page="editing"
					:modules="modules"
					@back="editing = null"
					@changed="changed"
					@visit="open = false"
				/>
				<template v-else>
					<SettingsHeader :title="group.label" :description="describe(group)" />
					<SettingsBody>
						<List
							:active="editing?.name"
							class="-mx-3 w-[calc(100%+1.5rem)] list-row-px-3"
							:columns="['minmax(0,1fr)', 'minmax(0,14rem)', '7rem']"
							:row-height="56"
						>
							<ListHeader>
								<ListHeaderCellSort
									v-for="[field, label] in [
										['title', __('Workspace')],
										['owner', __('Owner')],
										['access', __('Access')],
									]"
									:key="field"
									:direction="direction_for(field)"
									@click="toggle_sort(field)"
								>
									{{ label }}
									<template #sort-indicator="{ direction }">
										<span
											class="block size-3.5"
											:class="sort_icon(direction)"
										/>
									</template>
								</ListHeaderCellSort>
							</ListHeader>
							<ListRows
								v-slot="{ item: page, value }"
								:items="sorted(group.pages)"
								row-key="name"
							>
								<ListRow :value="value" @click="editing = page">
									<ListCell>
										<span class="truncate text-base text-ink-gray-8">
											{{ __(page.title) }}
										</span>
									</ListCell>
									<ListCell>
										<template v-if="page.for_user">
											<Avatar
												size="lg"
												:label="owner(page).name"
												:image="owner(page).image"
											/>
											<div class="ml-2.5 min-w-0">
												<div class="truncate text-base text-ink-gray-8">
													{{ owner(page).name }}
												</div>
												<div
													v-if="owner(page).name !== page.for_user"
													class="mt-0.5 truncate text-sm text-ink-gray-5"
												>
													{{ page.for_user }}
												</div>
											</div>
										</template>
									</ListCell>
									<ListCell>
										<Badge
											:label="access(page).label"
											:theme="access(page).theme"
										/>
									</ListCell>
								</ListRow>
							</ListRows>
						</List>
					</SettingsBody>
				</template>
			</SettingsPanel>
		</SettingsContent>
	</SettingsDialog>
</template>
