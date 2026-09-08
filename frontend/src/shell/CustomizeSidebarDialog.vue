<!--
  The customize dialog: reorder, hide, rename, one component for the rail or a panel, picked by
  the hash. It shows one scope deep with hidden rows and writes only on Save.
-->
<template>
	<Dialog :modelValue="!!target" size="sm" :title="target?.title" @update:modelValue="dismissed">
		<p v-if="failed" class="text-sm text-ink-red-4">
			{{ failed }}
		</p>

		<ul v-else data-testid="customize">
			<li
				v-for="item in items"
				:key="item.key"
				:data-key="item.key"
				:class="[
					'flex items-center gap-1 rounded px-1 py-1',
					item.parent_key ? 'ml-4' : '',
					item.hidden ? 'opacity-50' : '',
				]"
				draggable="true"
				@dragstart="dragging = item.key"
				@dragover.prevent
				@drop.prevent="drop(item.key)"
			>
				<input
					class="min-w-0 flex-1 rounded bg-transparent px-1 py-0.5 text-sm text-ink-gray-8 hover:bg-surface-gray-2 focus:bg-surface-gray-2"
					:value="item.label ?? ''"
					:placeholder="item.link_to ?? item.key"
					:aria-label="`Name of ${item.key}`"
					@input="rename(item.key, ($event.target as HTMLInputElement).value)"
				/>
				<!-- `lucide-` prefixed: frappe-ui's Button takes a CSS class, and a bare name
					 draws nothing. Literal here, so Tailwind's JIT emits the class. -->
				<Button
					variant="ghost"
					icon="lucide-chevron-up"
					:aria-label="`Move ${item.key} up`"
					@click="items = move(items, item.key, -1)"
				/>
				<Button
					variant="ghost"
					icon="lucide-chevron-down"
					:aria-label="`Move ${item.key} down`"
					@click="items = move(items, item.key, 1)"
				/>
				<Button
					variant="ghost"
					:icon="item.hidden ? 'lucide-eye-off' : 'lucide-eye'"
					:aria-label="`${item.hidden ? 'Show' : 'Hide'} ${item.key}`"
					@click="toggleHidden(item.key)"
				/>
			</li>
		</ul>

		<template #actions>
			<div class="flex justify-end gap-2">
				<Button label="Reset" :loading="busy" @click="reset" />
				<Button variant="solid" label="Save" :loading="busy" @click="save" />
			</div>
		</template>
	</Dialog>
</template>

<script lang="ts">
import type { Address } from "@/arrangement";

/** Which list the dialog shows, and the title over it. `null` keeps the dialog closed. */
export type CustomizeTarget = Address & { title: string };
</script>

<script setup lang="ts">
import { ref, watch } from "vue";
import { Button, Dialog } from "frappe-ui";
import type { Navigation } from "@/boot";
import {
	type Address,
	type ArrangedItem,
	dropOn,
	fetchArrangement,
	move,
	resetArrangement,
	saveArrangement,
} from "@/arrangement";

const props = defineProps<{ target: CustomizeTarget | null }>();
const emit = defineEmits<{ close: []; saved: [Navigation] }>();

const items = ref<ArrangedItem[]>([]);
const dragging = ref<string | null>(null);
const busy = ref(false);
const failed = ref<string | null>(null);

// Mounted once: the hash, not a mount, decides which list loads. A new target outranks any
// request still in flight for the last one, or a slow one could hand its rows to the wrong Save.
let generation = 0;

watch(
	() => props.target,
	(target) => {
		generation++;
		items.value = [];
		failed.value = null;
		dragging.value = null;
		if (target) load(target);
	},
	{ immediate: true }
);

async function load(target: Address) {
	const mine = generation;
	busy.value = true;
	try {
		const rows = await fetchArrangement(target);
		if (mine === generation) items.value = rows;
	} catch (error) {
		if (mine === generation)
			failed.value = `Could not load this list: ${(error as Error).message}`;
	} finally {
		if (mine === generation) busy.value = false;
	}
}

function dismissed(open: boolean) {
	if (!open) emit("close");
}

function rename(key: string, label: string) {
	// Replaced, not mutated, so a stale reference cannot leak an edit into a list already sent.
	items.value = items.value.map((item) => (item.key === key ? { ...item, label } : item));
}

function toggleHidden(key: string) {
	items.value = items.value.map((item) =>
		item.key === key ? { ...item, hidden: item.hidden ? undefined : (1 as const) } : item
	);
}

function drop(onto: string) {
	if (dragging.value) items.value = dropOn(items.value, dragging.value, onto);
	dragging.value = null;
}

async function save() {
	if (props.target) await write(saveArrangement(props.target, items.value));
}

async function reset() {
	if (!props.target) return;
	await write(resetArrangement(props.target));
	await load(props.target);
}

async function write(request: Promise<Navigation>) {
	const mine = generation;
	busy.value = true;
	try {
		emit("saved", await request);
	} catch (error) {
		if (mine === generation)
			failed.value = `Could not save this list: ${(error as Error).message}`;
	} finally {
		if (mine === generation) busy.value = false;
	}
}
</script>
