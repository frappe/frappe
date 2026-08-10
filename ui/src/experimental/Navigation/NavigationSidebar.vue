<template>
	<div class="flex flex-1 flex-col bg-inherit pb-2">
		<div
			v-if="navigation.loading.value && !navigation.fetched.value"
			class="flex flex-col gap-1 px-2 py-1.5"
		>
			<Skeleton v-for="n in 3" :key="n" class="h-7 w-full rounded" />
		</div>

		<div
			v-else-if="navigation.error.value && !navigation.fetched.value"
			class="px-2 py-1.5"
		>
			<ErrorMessage message="Could not load views" />
			<Button
				class="mt-1.5"
				variant="subtle"
				size="sm"
				label="Retry"
				@click="navigation.reload()"
			/>
		</div>

		<template v-else>
			<div
				v-for="(section, index) in sections"
				:key="section.name"
				class="mt-2 flex flex-col first:mt-0"
			>
				<hr v-if="section.isExtras && index > 0" class="mb-2 mt-1 border-outline-gray-1" />

				<div
					v-if="!section.isExtras || index === controlsIndex"
					class="flex h-7 items-center justify-between"
				>
					<SidebarLabel v-if="!section.isExtras" class="min-w-0 flex-1">
						{{ section.label }}
					</SidebarLabel>
					<Button
						v-if="index === controlsIndex"
						class="ml-auto shrink-0"
						variant="ghost"
						size="sm"
						icon="lucide-settings-2 text-ink-gray-5"
						label="Customize sidebar"
						tooltip="Customize sidebar"
						@click="isEditing = true"
					/>
				</div>

				<nav class="mt-0.5 flex flex-col gap-0.5">
					<NavigationSidebarItem
						v-for="row in section.rows"
						:key="row.item.name || row.item.label"
						:item="row.item"
						:to="row.to"
						:isActive="row.isActive"
						:count="row.count"
						:isStoredDefault="row.isStoredDefault"
						:canManageShared="navigation.canManageShared.value"
						@act="runAction"
					/>
				</nav>

				<p v-if="!section.rows.length" class="px-2 py-1.5 text-sm text-ink-gray-4">
					No saved views
				</p>
			</div>
		</template>

		<NavigationEditorDialog
			v-model="isEditing"
			:navigation="navigation"
			:itemKinds="itemKinds"
			:addOptions="addOptions"
			@open="run(() => navigation.loadPool())"
		/>

		<ViewFormDialog
			v-model="isFormOpen"
			:view="editing"
			:canShare="navigation.canManageShared.value"
			:onSubmit="saveForm"
		/>

		<Dialog v-model="isDeleteOpen" :options="{ title: 'Delete view' }">
			<template #body-content>
				<p class="text-p-base text-ink-gray-6">
					Delete “{{ pending?.label }}”? This cannot be undone. To keep the view but take
					it off the sidebar, use Remove from sidebar instead.
				</p>
			</template>
			<template #actions>
				<Button
					class="w-full"
					theme="red"
					variant="solid"
					label="Delete"
					@click="confirmDelete"
				/>
			</template>
		</Dialog>

		<ErrorMessage class="px-2" :message="actionError" />
	</div>
</template>

<script setup lang="ts">
import { computed, h, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Button, Dialog, ErrorMessage, Skeleton, SidebarLabel } from "frappe-ui";
import NavigationEditorDialog from "./NavigationEditorDialog.vue";
import NavigationSidebarItem from "./NavigationSidebarItem.vue";
import { ViewFormDialog, ViewIcon, useSavedViews, viewIdFromPath } from "../SavedViews";
import { useNavigation } from "./useNavigation";
import { isExtrasSection, withExtrasLast } from "./sections";
import { errorMessage } from "../errorMessage";
import type { ViewActionKind, SavedView, ViewFormValues } from "../SavedViews";
import type { ViewName } from "../SavedViews/savedViewApi";
import type {
	AddMenuOptions,
	NavigationItem,
	NavigationSidebarProps,
	PoolView,
} from "./types";

const props = defineProps<NavigationSidebarProps>();

const route = useRoute();
const router = useRouter();

const activeId = computed(() =>
	props.activeView !== undefined ? props.activeView : viewIdFromPath(route.path)
);

const navigation = useNavigation(() => props.doctype, activeId, {
	app: () => props.app,
});
const views = useSavedViews(() => props.doctype, {
	app: navigation.app,
	onChange: navigation.reload,
});

const basePath = computed(() => props.basePath ?? `/${encodeURIComponent(props.doctype)}`);

type Section = {
	name: string;
	label: string;
	isExtras: boolean;
	rows: ReturnType<typeof toRow>[];
};

const sections = computed<Section[]>(() => {
	const rendered = withExtrasLast(navigation.sections.value.filter((section) => !section.hidden))
		.map((section) => ({
			name: section.name,
			label: section.label,
			isExtras: isExtrasSection(section),
			rows: section.items.filter((item) => !item.hidden).map(toRow),
		}))
		.filter((section) => section.rows.length);

	if (rendered.length) return rendered;
	return [{ name: "", label: "Views", isExtras: false, rows: [virtualAll()] }];
});

const controlsIndex = computed(() => {
	const withHeading = sections.value.findIndex((section) => !section.isExtras);
	return withHeading === -1 ? 0 : withHeading;
});

const highlightId = computed(
	() => navigation.activeView.value?.name ?? navigation.defaultView.value ?? null
);

function toRow(item: NavigationItem) {
	if (!item.view)
		return { item, to: item.url, isActive: false, isStoredDefault: false, count: null };

	const isDefault = sameView(item.view.name, navigation.defaultView.value);
	return {
		item,
		to: isDefault ? basePath.value : pathOf(item.view.name),
		isActive: sameView(item.view.name, highlightId.value),
		isStoredDefault: isDefault && navigation.defaultViewIsStored.value,
		count: countOf(item.view.name),
	};
}

function virtualAll() {
	const view = {
		name: "",
		label: "All",
		reference_doctype: props.doctype,
		type: "list",
	} as SavedView;
	return {
		item: {
			name: "",
			type: "view" as const,
			label: view.label,
			icon: "",
			dt: "",
			url: "",
			new_tab: 0 as const,
			hidden: 0 as const,
			view,
		},
		to: basePath.value,
		isActive: !activeId.value,
		isStoredDefault: false,
		count: null,
	};
}

function sameView(a: string | number, b: string | number | null) {
	return b != null && String(a) === String(b);
}

function countOf(name: string | number): number | null {
	const value = navigation.counts.value[String(name)];
	return value ?? null;
}

function pathOf(name: string | number) {
	return `${basePath.value}/view/${encodeURIComponent(name)}`;
}

const isEditing = ref(false);
const isFormOpen = ref(false);
const isDeleteOpen = ref(false);
const editing = ref<SavedView | null>(null);
const pending = ref<SavedView | null>(null);
const actionError = ref("");

const countKey = computed(() =>
	navigation.visibleSections.value
		.flatMap((section) => section.items.map((item) => item.view?.name ?? ""))
		.join(",")
);

watch(
	[countKey, activeId],
	() => {
		if (countKey.value) navigation.loadCounts().catch(() => {});
	},
	{ immediate: true }
);

function addOptions(section: string | null): AddMenuOptions {
	return {
		items: [{ label: "View", icon: "filter", onClick: () => openCreate(section) }],
		groups: navigation.pool.value.length
			? [
					{
						group: "Add to sidebar",
						items: navigation.pool.value.map((view: PoolView) => ({
							label: view.label,
							slots: { prefix: () => h(ViewIcon, { icon: view.icon }) },
							onClick: () =>
								run(() =>
									keepVirtualAll(!view.user)
										.then(() => navigation.addToSidebar(view.name))
										.then((name) => placeInSection(name, section))
										.then(open)
								),
						})),
					},
				]
			: [],
	};
}

function placeInSection(view: ViewName, section: string | null) {
	if (!section) return Promise.resolve(view);
	return navigation.moveViewToSection(view, section).then(() => view);
}

const placingIn = ref<string | null>(null);

function openCreate(section: string | null) {
	placingIn.value = section;
	editing.value = null;
	isFormOpen.value = true;
}

async function saveForm(values: ViewFormValues) {
	if (editing.value) {
		await views.updateView(editing.value.name, {
			label: values.label,
			icon: values.icon,
		});
		return;
	}

	await keepVirtualAll(Boolean(values.shared));
	await views.createView({ ...values, section: placingIn.value }).then(open);
}

function keepVirtualAll(shared: boolean) {
	if (navigation.sections.value.length) return Promise.resolve();
	return views.createView({ label: "All", icon: "list", shared });
}

const handlers: Record<ViewActionKind, (view: SavedView) => Promise<unknown>> = {
	edit: async (view) => {
		editing.value = view;
		isFormOpen.value = true;
	},
	duplicate: (view) => views.duplicateView(view.name).then(open),
	setDefault: (view) => views.setAsDefault(view.name),
	makeShared: (view) => views.moveView(view.name, true),
	makePersonal: (view) => views.moveView(view.name, false),
	removeFromSidebar: (view) => navigation.removeFromSidebar(view.name),
	delete: async (view) => {
		pending.value = view;
		isDeleteOpen.value = true;
	},
};

function runAction(kind: ViewActionKind, item: NavigationItem) {
	if (item.view) run(() => handlers[kind](item.view as SavedView));
}

function confirmDelete() {
	const view = pending.value;
	isDeleteOpen.value = false;
	if (view) run(() => views.deleteView(view.name));
}

async function run(operation: () => Promise<unknown>) {
	actionError.value = "";
	try {
		await operation();
	} catch (exception) {
		actionError.value = errorMessage(exception);
	}
}

function open(name: string | number) {
	router.push(pathOf(name));
	return name;
}
</script>
