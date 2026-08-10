<template>
	<div ref="editor" class="flex flex-1 flex-col gap-2 bg-inherit">
		<div
			v-if="canManageShared"
			class="sticky top-0 z-10 flex h-7 items-center justify-between bg-inherit"
		>
			<span :class="GROUP_LABEL_CLASS">Editing for</span>
			<Select v-model="scope" :options="scopeOptions" aria-label="Editing for" />
		</div>

		<div class="flex flex-col gap-1.5" :class="flat && canManageShared ? 'mt-2' : ''">
			<span v-if="flat" :class="GROUP_LABEL_CLASS">Shown in sidebar</span>
			<Draggable
				:class="flat ? BOX_CLASS : 'flex flex-col gap-3'"
				:modelValue="draft"
				:item-key="(section: NavigationSection) => section.name"
				handle=".section-drag-handle"
				tag="div"
				@update:modelValue="reorderSections"
			>
				<template #item="{ element: section }">
					<NavigationSidebarEditSection
						:section="section"
						:items="flat ? shownRows[section.name] : undefined"
						:box="flat ? 'shown' : undefined"
						:forEveryone="forEveryone"
						:canManageShared="canManageShared"
						:flat="flat"
						:canDelete="draft.length > 1"
						:addOptions="flat ? undefined : addItemOptions(section)"
						@change="onDrop"
						@toggleHidden="onToggleHidden"
						@toggleSectionHidden="
							(target) => run(navigation.hideSection(target.name, !target.hidden))
						"
						@remove="removeRow"
						@setViewIcon="setViewIcon"
						@edit="startEditing"
						@update="
							(target, item, naming) =>
								run(navigation.updateItem(target.name, item.name, naming, forEveryone))
						"
						@rename="(target, label) => run(navigation.renameSection(target.name, label))"
						@delete="confirmingDelete = $event"
					/>
				</template>

				<template #footer>
					<Dropdown v-if="flat" :options="addItemOptions(null)" align="start">
						<button type="button" :class="[ADD_CLASS, ROW_INSET_CLASS]">
							<span class="lucide-plus size-3.5 shrink-0" aria-hidden="true" />
							Add item
						</button>
					</Dropdown>
				</template>
			</Draggable>
		</div>

		<div v-if="flat && !forEveryone" class="mt-2 flex flex-col gap-1.5">
			<span :class="GROUP_LABEL_CLASS">Hidden from sidebar</span>
			<div :class="BOX_CLASS">
				<NavigationSidebarEditSection
					v-for="section in draft"
					:key="section.name"
					:section="section"
					:items="hiddenRows[section.name]"
					box="hidden"
					:forEveryone="forEveryone"
					:canManageShared="canManageShared"
					flat
					:canDelete="false"
					@change="onDrop"
					@toggleHidden="onToggleHidden"
					@remove="removeRow"
					@setViewIcon="setViewIcon"
					@edit="startEditing"
					@update="
						(target, item, naming) =>
							run(navigation.updateItem(target.name, item.name, naming, forEveryone))
					"
				/>
			</div>
		</div>

		<div v-if="!flat" class="flex flex-col gap-0.5">
			<Dropdown v-if="!draft.length" :options="addItemOptions(null)" align="start">
				<button type="button" :class="[ADD_CLASS, ADD_OUTSIDE_CLASS]">
					<span class="lucide-plus size-3.5 shrink-0" aria-hidden="true" />
					Add item
				</button>
			</Dropdown>

			<button type="button" :class="[ADD_CLASS, ADD_OUTSIDE_CLASS]" @click="addSection">
				<span class="lucide-plus size-3.5 shrink-0" aria-hidden="true" />
				Add section
			</button>
		</div>

		<NavigationItemFormDialog
			v-if="formKind"
			v-model="isFormOpen"
			:kind="formKind"
			:initial="editing?.values"
			:onSubmit="submitItem"
			@after-leave="focusAddedItem"
		/>

		<Dialog v-model="isFlipOpen" :options="{ title: 'Change who can see this view' }">
			<template #body-content>
				<p class="text-p-base text-ink-gray-6">{{ flipMessage }}</p>
			</template>
			<template #actions>
				<Button class="w-full" variant="solid" label="Move it" @click="applyFlip" />
			</template>
		</Dialog>

		<Dialog v-model="isDeleteOpen" :options="{ title: 'Delete section' }">
			<template #body-content>
				<p class="text-p-base text-ink-gray-6">
					Delete “{{ confirmingDelete?.label }}”? Its views drop back to the pool and the
					+ menu can add them again — no view is deleted.
				</p>
			</template>
			<template #actions>
				<Button
					class="w-full"
					theme="red"
					variant="solid"
					label="Delete section"
					@click="applyDelete"
				/>
			</template>
		</Dialog>
	</div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, useTemplateRef, watch } from "vue";
import { Button, Dialog, Dropdown, Select } from "frappe-ui";
// @ts-ignore — vuedraggable ships no bundled types
import Draggable from "vuedraggable";
import NavigationItemFormDialog from "./NavigationItemFormDialog.vue";
import NavigationSidebarEditSection from "./NavigationSidebarEditSection.vue";
import {
	findSourceSection,
	flipsVisibility,
	holdsItem,
	toBoxedRows,
	toRows,
	withHidden,
} from "./arrangement";
import {
	ADD_CLASS,
	ADD_OUTSIDE_CLASS,
	BOX_CLASS,
	GROUP_LABEL_CLASS,
	ROW_INSET_CLASS,
} from "./editorStyles";
import { addableKinds, itemValues, kindMenuOptions } from "./itemKinds";
import { findExtrasSection, findFlatSection } from "./sections";
import { savedViewApi } from "../SavedViews/savedViewApi";
import type { NavigationItemFormValues, NavigationItemKind } from "./itemKinds";
import type { UseNavigation } from "./useNavigation";
import type { SavedView } from "../SavedViews";
import type {
	AddMenuOptions,
	ArrangedRow,
	DragChange,
	NavigationItem,
	NavigationSection,
} from "./types";

const NEW_SECTION_LABEL = "New section";
const EXTRAS_SECTION_LABEL = "More";

const SCOPE_LABELS = { personal: "Just me", shared: "Everyone" };

const props = defineProps<{
	navigation: UseNavigation;
	canManageShared: boolean;
	itemKinds?: NavigationItemKind[];
	addOptions?: (section: string | null) => AddMenuOptions;
	flat?: boolean;
}>();

const emit = defineEmits<{ error: [message: unknown] }>();

const navigation = props.navigation;

const forEveryone = ref(false);

const scopeOptions = [
	{ label: SCOPE_LABELS.personal, value: "personal" },
	{ label: SCOPE_LABELS.shared, value: "shared" },
];

const scope = computed({
	get: () => (forEveryone.value ? "shared" : "personal"),
	set: (value) => setScope(value === "shared"),
});

async function setScope(everyone: boolean) {
	try {
		if (everyone) await navigation.loadShared();
	} catch (exception) {
		return emit("error", exception);
	}
	forEveryone.value = everyone;
}

const arrangement = computed(() =>
	forEveryone.value ? navigation.sharedSections.value : navigation.sections.value
);

const draft = ref<NavigationSection[]>([]);

const shownRows = ref<Record<string, NavigationItem[]>>({});
const hiddenRows = ref<Record<string, NavigationItem[]>>({});

watch(
	arrangement,
	(sections) => {
		draft.value = sections.map((section) => ({ ...section, items: [...section.items] }));
		shownRows.value = splitBy(sections, (item) => !item.hidden);
		hiddenRows.value = splitBy(sections, (item) => Boolean(item.hidden));
	},
	{ immediate: true, deep: true }
);

function splitBy(sections: NavigationSection[], keep: (item: NavigationItem) => boolean) {
	return Object.fromEntries(
		sections.map((section) => [section.name, section.items.filter(keep)])
	);
}

const pendingFlip = ref<{ view: SavedView; section: NavigationSection; index: number } | null>(
	null
);
const confirmingDelete = ref<NavigationSection | null>(null);

const isFlipOpen = computed({
	get: () => Boolean(pendingFlip.value),
	set: (open) => {
		if (open) return;
		pendingFlip.value = null;
		navigation.reload();
	},
});
const isDeleteOpen = computed({
	get: () => Boolean(confirmingDelete.value),
	set: (open) => !open && (confirmingDelete.value = null),
});

const flipMessage = computed(() => {
	const target = pendingFlip.value?.section;
	if (!target) return "";
	return target.user
		? `“${pendingFlip.value?.view.label}” is shared with everyone. Moving it into “${target.label}” makes it visible only to you.`
		: `“${pendingFlip.value?.view.label}” is yours alone. Moving it into “${target.label}” shares it with everyone.`;
});

function onDrop(section: NavigationSection, change: DragChange) {
	if (change.added) return onAdded(section, change.added);
	if (change.moved) return arrange(section, rowsOf(section));
}

function onAdded(
	section: NavigationSection,
	added: { element: NavigationItem; newIndex: number }
) {
	if (props.flat && holdsItem(arrangement.value, section, added.element))
		return arrange(section, rowsOf(section));

	const source = findSourceSection(arrangement.value, added.element, section);
	const view = added.element.view;

	if (!view) {
		if (!source) return run(navigation.reload());
		return run(
			navigation.moveItemToSection(
				source.name,
				added.element.name,
				section.name,
				added.newIndex,
				forEveryone.value
			)
		);
	}

	if (source && flipsVisibility(source, section)) {
		pendingFlip.value = { view, section, index: added.newIndex };
		return;
	}
	run(navigation.moveViewToSection(view.name, section.name, added.newIndex));
}

function onToggleHidden(section: NavigationSection, item: NavigationItem) {
	run(navigation.arrangeItems(section.name, withHidden(section.items, item.name, !item.hidden)));
}

function removeRow(section: NavigationSection, item: NavigationItem) {
	if (item.view) return run(navigation.removeFromSidebar(item.view.name));
	run(navigation.removeItem(section.name, item.name));
}

function setViewIcon(view: SavedView, icon: string) {
	run(savedViewApi.update(view.name, { icon }).then(() => navigation.reload()));
}

function arrange(section: NavigationSection, rows: ArrangedRow[]) {
	run(navigation.arrangeItems(section.name, rows, forEveryone.value));
}

function applyFlip() {
	const pending = pendingFlip.value;
	pendingFlip.value = null;
	if (pending)
		run(navigation.moveViewToSection(pending.view.name, pending.section.name, pending.index));
}

function applyDelete() {
	const section = confirmingDelete.value;
	confirmingDelete.value = null;
	if (section) run(navigation.deleteSection(section.name));
}

const formKind = ref<NavigationItemKind | null>(null);
const isFormOpen = ref(false);
const editing = ref<{
	section: NavigationSection;
	item: NavigationItem;
	values: NavigationItemFormValues;
} | null>(null);
const addingTo = ref<NavigationSection | null>(null);

function addItemOptions(section: NavigationSection | null) {
	const host = props.addOptions?.(section?.name ?? null);
	return [
		...(host?.items ?? []),
		...kindMenuOptions(props.itemKinds, (kind) => startAdding(kind, section)),
		...(host?.groups ?? []),
	];
}

function startAdding(kind: NavigationItemKind, section: NavigationSection | null) {
	editing.value = null;
	addingTo.value = section;
	formKind.value = kind;
	isFormOpen.value = true;
}

async function startEditing(section: NavigationSection, item: NavigationItem) {
	const kind = addableKinds(props.itemKinds).find((candidate) => candidate.type === item.type);
	if (!kind) return;

	addingTo.value = null;

	try {
		const stored = await navigation.getItem(section.name, item.name);
		editing.value = {
			section,
			item,
			values: { target: stored[kind.field] ?? "", label: item.label, icon: item.icon },
		};
	} catch (exception) {
		return emit("error", exception);
	}

	formKind.value = kind;
	isFormOpen.value = true;
}

function submitItem(values: NavigationItemFormValues) {
	return editing.value ? saveItem(values) : addItem(values);
}

async function saveItem(values: NavigationItemFormValues) {
	const target = editing.value;
	const kind = formKind.value;
	if (!target || !kind) return;

	await navigation.updateItem(
		target.section.name,
		target.item.name,
		{ label: values.label, icon: values.icon },
		forEveryone.value,
		{ [kind.field]: values.target }
	);
}

async function addItem(values: NavigationItemFormValues) {
	const kind = formKind.value;
	if (!kind) return;

	const target =
		addingTo.value ??
		(props.flat
			? findFlatSection(arrangement.value, forEveryone.value)
			: findExtrasSection(arrangement.value, forEveryone.value));
	const created = target
		? ""
		: await navigation.createSection(EXTRAS_SECTION_LABEL, forEveryone.value);

	try {
		addedItem.value = await navigation.addItem(
			target?.name ?? created,
			itemValues(kind, values),
			forEveryone.value
		);
	} catch (exception) {
		if (created) await navigation.deleteSection(created);
		throw exception;
	}
}

function addSection() {
	run(navigation.createSection(NEW_SECTION_LABEL, forEveryone.value));
}

const editor = useTemplateRef<HTMLElement>("editor");
const addedItem = ref("");

async function focusAddedItem() {
	if (!addedItem.value) return;
	await nextTick();
	const row = editor.value?.querySelector<HTMLElement>(`[data-item="${addedItem.value}"]`);
	addedItem.value = "";
	row?.scrollIntoView({ block: "nearest" });
	row?.focus();
}

function reorderSections(sections: NavigationSection[]) {
	draft.value = sections;
	run(
		navigation.arrangeSections(
			sections.map((section) => section.name),
			forEveryone.value
		)
	);
}

function rowsOf(section: NavigationSection): ArrangedRow[] {
	if (props.flat)
		return toBoxedRows(shownRows.value[section.name] ?? [], hiddenRows.value[section.name] ?? []);

	const dragged = draft.value.find((candidate) => candidate.name === section.name);
	return toRows(dragged?.items ?? section.items);
}

async function run(operation: Promise<unknown>) {
	try {
		await operation;
	} catch (exception) {
		emit("error", exception);
		navigation.reload();
	}
}
</script>
