<!--
  The arrangement editor: reorder, hide, rename, one component for either container. It shows one
  scope deep with hidden rows, writes only on Save, and uses the platform's own drag events plus arrows.
-->
<template>
	<div class="flex w-80 shrink-0 flex-col border-l border-outline-gray-2 bg-surface-white">
		<header class="flex items-center justify-between border-b border-outline-gray-2 p-3">
			<h2 class="text-base font-medium text-ink-gray-8">{{ title }}</h2>
			<Button variant="ghost" label="Close" @click="emit('close')" />
		</header>

		<p v-if="failed" class="p-3 text-sm text-ink-red-4">
			{{ failed }}
		</p>

		<ul v-else class="flex-1 overflow-y-auto p-2" data-testid="arrangement">
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

		<footer class="flex items-center gap-2 border-t border-outline-gray-2 p-3">
			<Button variant="solid" label="Save" :loading="busy" @click="save" />
			<Button label="Reset" :loading="busy" @click="reset" />
		</footer>
	</div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { Button } from "frappe-ui";
import type { Navigation } from "@/boot";
import {
	type ArrangedItem,
	type Container,
	dropOn,
	fetchArrangement,
	move,
	resetArrangement,
	saveArrangement,
} from "@/arrangement";

const props = defineProps<{ container: Container; address: string; title: string }>();
const emit = defineEmits<{ close: []; saved: [Navigation] }>();

const items = ref<ArrangedItem[]>([]);
const dragging = ref<string | null>(null);
const busy = ref(false);
// A message, not a boolean: an editor that failed to load must not read as "nothing to arrange".
const failed = ref<string | null>(null);

onMounted(load);

async function load() {
	try {
		items.value = await fetchArrangement(props);
	} catch (error) {
		failed.value = `Could not load this arrangement: ${(error as Error).message}`;
	}
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
	await write(() => saveArrangement(props, items.value));
}

async function reset() {
	await write(() => resetArrangement(props));
	await load();
}

async function write(request: () => Promise<Navigation>) {
	busy.value = true;
	try {
		emit("saved", await request());
	} catch (error) {
		failed.value = `Could not save this arrangement: ${(error as Error).message}`;
	} finally {
		busy.value = false;
	}
}
</script>
