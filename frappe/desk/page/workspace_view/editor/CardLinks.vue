<script setup>
import { nextTick, ref } from "vue";
import { Button, Select } from "frappe-ui";
import { List, ListCell, ListHeader, ListHeaderCell, ListRow } from "frappe-ui/list";
import { Link } from "@framework/ui";

// A card's links, edited in place: `{label, link_type, link_to}`, and `widget` for a saved Link
// widget. Changing what a saved link opens makes it a new link.
const props = defineProps({
	links: { type: Array, required: true },
});

const emit = defineEmits(["change"]);
const __ = window.__;

const LINK_TYPES = ["DocType", "Report", "Page"];
const type_options = LINK_TYPES.map((value) => ({ label: __(value), value }));

function changed() {
	emit("change");
}

function add_link() {
	props.links.push({ link_type: "DocType", link_to: "", label: "" });
	changed();
}

function set_type(link, value) {
	link.link_type = value;
	delete link.widget;
	changed();
}

// A link is named after what it opens, unless the editor gave it a name of its own.
function set_link_to(link, value) {
	if (!link.label || link.label === link.link_to) link.label = value;
	link.link_to = value;
	delete link.widget;
	changed();
}

// A link moves by its grip: dragged onto another row, or with the arrow keys.
const dragged = ref(null);
const drop_at = ref(null);

function move_link(from, to) {
	if (to < 0 || to >= props.links.length || from === to) return;
	props.links.splice(to, 0, props.links.splice(from, 1)[0]);
	changed();
}

function start_drag(event, index) {
	dragged.value = index;
	event.dataTransfer.effectAllowed = "move";
	const row = event.target.closest("[data-slot=list-row]") || event.target;
	event.dataTransfer.setDragImage(row, 12, 12);
}

function drop_link(index) {
	if (dragged.value !== null) move_link(dragged.value, index);
	dragged.value = drop_at.value = null;
}

function on_grip_key(event, index) {
	const step = { ArrowUp: -1, ArrowDown: 1 }[event.key];
	if (!step) return;
	event.preventDefault();
	move_link(index, index + step);
	const grips = event.currentTarget.closest("[data-slot=list]").querySelectorAll(".link-grip");
	nextTick(() => grips[index + step]?.focus());
}

function remove_link(index) {
	props.links.splice(index, 1);
	changed();
}
</script>

<template>
	<div class="col-span-2 flex flex-col gap-2 pt-2">
		<span class="text-sm text-ink-gray-6">{{ __("Links") }}</span>
		<List
			v-if="links.length"
			:columns="['1rem', '6.5rem', 'minmax(0,1fr)', '1.75rem']"
			divider="none"
			class="list-gap-2"
		>
			<ListHeader>
				<ListHeaderCell />
				<ListHeaderCell>
					<span class="text-xs text-ink-gray-5">{{ __("Type") }}</span>
				</ListHeaderCell>
				<ListHeaderCell>
					<span class="text-xs text-ink-gray-5">{{ __("Opens") }}</span>
				</ListHeaderCell>
				<ListHeaderCell />
			</ListHeader>
			<ListRow
				v-for="(link, index) in links"
				:key="index"
				class="group/row rounded-3 py-0.5"
				:class="[
					dragged === index && 'opacity-50',
					drop_at === index && dragged !== index && 'bg-surface-gray-2',
				]"
				@dragover.prevent="drop_at = index"
				@dragleave="drop_at === index && (drop_at = null)"
				@drop.prevent="drop_link(index)"
			>
				<ListCell>
					<button
						type="button"
						draggable="true"
						class="link-grip grid h-7 w-4 cursor-grab place-items-center rounded-2 text-ink-gray-4 hover:text-ink-gray-7 focus-visible:text-ink-gray-7 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3 active:cursor-grabbing"
						:aria-label="__('Move {0}', [link.label || __('link')])"
						:title="__('Drag to reorder')"
						@dragstart="start_drag($event, index)"
						@dragend="dragged = drop_at = null"
						@keydown="on_grip_key($event, index)"
					>
						<span class="lucide-grip-vertical size-3.5" aria-hidden="true" />
					</button>
				</ListCell>
				<ListCell class="[&_[data-slot=trigger]]:w-full">
					<Select
						variant="outline"
						:aria-label="__('Type')"
						:options="type_options"
						:model-value="link.link_type"
						@update:model-value="(value) => set_type(link, value)"
					/>
				</ListCell>
				<ListCell class="[&_[data-slot=trigger]]:w-full [&>*]:w-full">
					<Link
						:key="link.link_type"
						variant="outline"
						:aria-label="__('Opens')"
						:doctype="link.link_type"
						:model-value="link.link_to"
						@update:model-value="(value) => set_link_to(link, value)"
					/>
				</ListCell>
				<ListCell>
					<Button
						class="opacity-0 group-hover/row:opacity-100 focus-visible:opacity-100"
						size="sm"
						variant="ghost"
						icon="lucide-x"
						:label="__('Remove link')"
						@click="remove_link(index)"
					/>
				</ListCell>
			</ListRow>
		</List>
		<Button
			class="self-start"
			size="sm"
			icon-left="lucide-plus"
			:label="__('Add link')"
			@click="add_link"
		/>
	</div>
</template>
