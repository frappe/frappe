<!--
  The arrangement editor: reorder, hide, rename, on either container.

  ONE component for the rail and for a sidebar, because they are one model. It takes a container
  and an address and nothing else about which surface it is editing — the moment it branched on
  that, desk v2 would have desk v1's shape, where one base class and two subclasses spend about
  1,800 lines saying the same thing twice.

  It shows the list ONE SCOPE DEEP, hidden rows included, which is not what the rail shows. A
  person cannot unhide what they cannot see, so an editor that rendered `boot.navigation` would
  make hiding a one-way door.

  A drag saves nothing on its own, and neither does an arrow or a rename. The write is the Save
  button, and until then every edit is local — the same choice desk v1 made, and it is a choice
  rather than a constraint: a save costs a request and a round trip that replaces the whole of
  `boot.navigation`, which is not what anybody wants per keystroke.

  There is no drag library. `sortablejs` and `vuedraggable` sit in the lockfile but are asked for
  by neither `package.base.json` nor frappe-ui, so adopting one would be a new shared dependency
  under #42069's singleton rule — a real cost, weighed here against about fifteen lines of the
  platform's own drag events. The arrows are not a fallback for the drag; they are the half that
  works from a keyboard.
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
// A message rather than a boolean. An editor that failed to load its list is indistinguishable
// from one whose navigation is empty, and "you have nothing to arrange" is a false statement to
// put over a request that never landed.
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
	// The whole row is replaced rather than mutated, so `items` is a list of values and a stale
	// reference cannot leak an edit into a list this has already sent.
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
