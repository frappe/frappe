<template>
	<div class="flex flex-col" :class="flat ? 'gap-0.5' : 'gap-1.5'">
		<div v-if="!flat" class="group/section flex h-7 items-center gap-1.5">
			<span
				class="section-drag-handle lucide-grip-vertical -ms-1 size-3.5 shrink-0 cursor-grab text-ink-gray-4"
				aria-hidden="true"
			/>

			<TextInput
				v-if="isRenaming"
				ref="renameInput"
				class="-ms-2 min-w-0 flex-1"
				variant="ghost"
				size="sm"
				:modelValue="section.label"
				:aria-label="`Rename ${section.label}`"
				@change="rename"
				@blur="isRenaming = false"
				@keydown.enter="($event.target as HTMLInputElement).blur()"
				@keydown.esc="isRenaming = false"
			/>

			<template v-else>
				<span
					class="min-w-0 flex-1 truncate"
					:class="section.hidden ? GROUP_LABEL_DIMMED_CLASS : GROUP_LABEL_CLASS"
					@dblclick="canEdit && startRenaming()"
				>
					{{ section.label }}
				</span>

				<Button
					v-if="!forEveryone"
					class="shrink-0 transition-opacity"
					:class="
						section.hidden
							? 'opacity-100'
							: 'opacity-0 group-hover/section:opacity-100 group-focus-within/section:opacity-100'
					"
					variant="ghost"
					size="xs"
					:icon="`${section.hidden ? 'lucide-eye-off' : 'lucide-eye'} text-ink-gray-5`"
					:label="`${section.hidden ? 'Show' : 'Hide'} ${section.label}`"
					:tooltip="section.hidden ? 'Show in sidebar' : 'Hide from sidebar'"
					@click="emit('toggleSectionHidden', section)"
				/>

				<Button
					v-if="canEdit"
					:class="SECTION_ACTION_CLASS"
					variant="ghost"
					size="xs"
					icon="lucide-pencil text-ink-gray-5"
					:label="`Rename ${section.label}`"
					tooltip="Rename"
					@click="startRenaming"
				/>
				<Button
					v-if="canEdit && canDelete"
					:class="SECTION_ACTION_CLASS"
					variant="ghost"
					size="xs"
					icon="lucide-trash-2 text-ink-gray-5"
					:label="`Delete ${section.label}`"
					tooltip="Delete section"
					@click="emit('delete', section)"
				/>
			</template>
		</div>

		<Draggable
			class="flex-1"
			:class="flat ? 'flex flex-col gap-0.5' : BOX_CLASS"
			:list="rows"
			:item-key="(item: NavigationItem) => item.name"
			:group="{ name: 'navigation-items' }"
			handle=".item-drag-handle"
			tag="div"
			@change="emit('change', section, $event)"
		>
			<template #item="{ element: item }">
				<div
					class="group/row flex h-7 items-center gap-1.5 rounded pr-0.5 transition hover:bg-surface-gray-2 focus:focus-ring"
					:class="[
						item.hidden && !box ? 'text-ink-gray-4' : 'text-ink-gray-6',
						ROW_INSET_CLASS,
					]"
					:data-item="item.name"
					tabindex="-1"
				>
					<span
						class="item-drag-handle lucide-grip-vertical size-3.5 shrink-0 cursor-grab text-ink-gray-4"
						aria-hidden="true"
					/>
					<IconPicker
						v-if="canPickIcon(item)"
						:modelValue="item.icon"
						:sections="iconSections"
						@update:modelValue="(icon: string) => setIcon(item, icon)"
					>
						<template #trigger>
							<button
								type="button"
								class="-mx-1 grid size-6 shrink-0 cursor-pointer place-items-center rounded transition hover:bg-surface-gray-3 focus-visible:focus-ring"
								:aria-label="`Change icon for ${item.label}`"
							>
								<Tooltip text="Change icon">
									<span class="grid place-items-center">
										<ViewIcon :icon="item.icon" />
									</span>
								</Tooltip>
							</button>
						</template>
					</IconPicker>
					<span v-else class="grid size-4 shrink-0 place-items-center">
						<ViewIcon :icon="item.icon" />
					</span>

					<input
						v-if="renamingItem === item.name"
						:ref="selectOnMount"
						class="min-w-0 flex-1 border-0 bg-transparent p-0 text-sm text-ink-gray-6 focus:border-0 focus:outline-none focus:ring-0"
						:value="item.label"
						:aria-label="`Rename ${item.label}`"
						autocomplete="off"
						@change="renameItem(item, $event)"
						@blur="renamingItem = ''"
						@keydown.enter="($event.target as HTMLInputElement).blur()"
						@keydown.esc="renamingItem = ''"
					/>
					<span
						v-else
						class="min-w-0 flex-1 truncate text-sm"
						@dblclick="isNameable(item) && startRenamingItem(item)"
					>
						{{ item.label }}
					</span>

					<Button
						v-if="isNameable(item) && renamingItem !== item.name"
						class="shrink-0 opacity-0 transition-opacity group-hover/row:opacity-100 group-focus-within/row:opacity-100"
						variant="ghost"
						size="xs"
						icon="lucide-pencil text-ink-gray-5"
						:label="`${canEditItem(item) ? 'Edit' : 'Rename'} ${item.label}`"
						:tooltip="canEditItem(item) ? 'Edit' : 'Rename'"
						@click="
							canEditItem(item)
								? emit('edit', section, item)
								: startRenamingItem(item)
						"
					/>
					<Button
						v-if="!forEveryone"
						class="shrink-0 transition-opacity"
						:class="
							item.hidden && !box
								? 'opacity-100'
								: 'opacity-0 group-hover/row:opacity-100 group-focus-within/row:opacity-100'
						"
						variant="ghost"
						size="xs"
						:icon="`${visibilityIcon(item)} text-ink-gray-5`"
						:label="`${item.hidden ? 'Show' : 'Hide'} ${item.label}`"
						:tooltip="item.hidden ? 'Show in sidebar' : 'Hide from sidebar'"
						@click="emit('toggleHidden', section, item)"
					/>
					<Button
						v-if="canRemove(item)"
						class="shrink-0 opacity-0 transition-opacity group-hover/row:opacity-100 group-focus-within/row:opacity-100"
						variant="ghost"
						size="xs"
						icon="lucide-x text-ink-gray-5"
						:label="`Remove ${item.label}`"
						tooltip="Remove from sidebar"
						@click="emit('remove', section, item)"
					/>
				</div>
			</template>

			<template #footer>
				<p
					v-if="!rows.length"
					class="mr-0.5 flex h-7 items-center text-sm text-ink-gray-4"
					:class="ROW_INSET_CLASS"
				>
					{{ box === "hidden" ? "Drag here to hide" : "Drag an item here" }}
				</p>

				<Dropdown v-if="addOptions" :options="addOptions" align="start">
					<button type="button" :class="[ADD_CLASS, ROW_INSET_CLASS]">
						<span class="lucide-plus size-3.5 shrink-0" aria-hidden="true" />
						Add item
					</button>
				</Dropdown>
			</template>
		</Draggable>
	</div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, useTemplateRef } from "vue";
import { Button, Dropdown, TextInput, Tooltip } from "frappe-ui";
// @ts-ignore — vuedraggable ships no bundled types
import Draggable from "vuedraggable";
import { ViewIcon } from "../SavedViews";
import { canEditView } from "../SavedViews/viewActions";
import { IconPicker, useCustomIcons } from "../IconPicker";
import { canEditItem as mayEditItem, canEditSection } from "./arrangement";
import {
	ADD_CLASS,
	BOX_CLASS,
	GROUP_LABEL_CLASS,
	GROUP_LABEL_DIMMED_CLASS,
	ROW_INSET_CLASS,
} from "./editorStyles";
import type { SavedView } from "../SavedViews/types";
import type {
	AddMenuItem,
	DragChange,
	NavigationItem,
	NavigationItemNaming,
	NavigationSection,
} from "./types";

const props = defineProps<{
	section: NavigationSection;
	items?: NavigationItem[];
	box?: "shown" | "hidden";
	forEveryone: boolean;
	canManageShared: boolean;
	flat?: boolean;
	canDelete: boolean;
	addOptions?: AddMenuItem[];
}>();

const emit = defineEmits<{
	change: [section: NavigationSection, event: DragChange];
	toggleHidden: [section: NavigationSection, item: NavigationItem];
	toggleSectionHidden: [section: NavigationSection];
	remove: [section: NavigationSection, item: NavigationItem];
	edit: [section: NavigationSection, item: NavigationItem];
	update: [section: NavigationSection, item: NavigationItem, naming: NavigationItemNaming];
	setViewIcon: [view: SavedView, icon: string];
	rename: [section: NavigationSection, label: string];
	delete: [section: NavigationSection];
}>();

const canEdit = computed(() => canEditSection(props.section, props.forEveryone));

const rows = computed(() => props.items ?? props.section.items);

function canEditItem(item: NavigationItem) {
	return mayEditItem(props.section, item, props.forEveryone);
}

const { sections: iconSections } = useCustomIcons();

function visibilityIcon(item: NavigationItem) {
	if (!props.box) return item.hidden ? "lucide-eye-off" : "lucide-eye";
	return props.box === "hidden" ? "lucide-arrow-up" : "lucide-arrow-down";
}

function isNameable(item: NavigationItem) {
	return !item.view;
}

function canPickIcon(item: NavigationItem) {
	return item.view ? canEditView(item.view, props.canManageShared) : isNameable(item);
}

function canRemove(item: NavigationItem) {
	return item.view ? canEditView(item.view, props.canManageShared) : canEditItem(item);
}

const SECTION_ACTION_CLASS =
	"shrink-0 opacity-0 transition-opacity group-hover/section:opacity-100 group-focus-within/section:opacity-100";

const isRenaming = ref(false);
const renameInput = useTemplateRef<{ el: HTMLInputElement | null }>("renameInput");

async function startRenaming() {
	isRenaming.value = true;
	await nextTick();
	renameInput.value?.el?.select();
}

function rename(event: Event) {
	const label = (event.target as HTMLInputElement).value.trim();
	if (label && label !== props.section.label) emit("rename", props.section, label);
}

const renamingItem = ref("");

function startRenamingItem(item: NavigationItem) {
	renamingItem.value = item.name;
}

function selectOnMount(element: unknown) {
	(element as HTMLInputElement | null)?.select();
}

function renameItem(item: NavigationItem, event: Event) {
	const label = (event.target as HTMLInputElement).value.trim();
	if (label && label !== item.label)
		emit("update", props.section, item, { label, icon: item.icon });
}

function setIcon(item: NavigationItem, icon: string) {
	if (item.view) return emit("setViewIcon", item.view, icon);
	emit("update", props.section, item, { label: item.label, icon });
}
</script>
