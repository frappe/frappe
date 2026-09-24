<!--
  The customize dialog: reorder, hide, rename, one component for the rail or a panel, picked by
  the hash. It shows one scope deep with hidden rows and writes only on Save.
-->
<template>
	<Dialog :modelValue="!!target" size="sm" :title="target?.title" @update:modelValue="dismissed">
		<p v-if="failed" class="text-sm text-ink-red-4">
			{{ failed }}
		</p>

		<template v-else-if="loading">
			<LoadingStatus />
			<ul aria-hidden="true" data-customize-skeleton>
				<li v-for="row in 5" :key="row" class="flex items-center gap-1 px-1 py-1">
					<Skeleton class="h-6 min-w-0 flex-1 rounded-4" />
					<Skeleton
						v-for="control in 3"
						:key="control"
						class="size-7 shrink-0 rounded-4"
					/>
				</li>
			</ul>
		</template>

		<ul v-else data-testid="customize">
			<li
				v-for="item in items"
				:key="item.key"
				:data-key="item.key"
				:class="[
					'flex items-center gap-1 rounded-4 px-1 py-1',
					item.parent_key ? 'ml-4' : '',
					item.hidden ? 'opacity-50' : '',
				]"
				draggable="true"
				@dragstart="dragging = item.key"
				@dragover.prevent
				@drop.prevent="drop(item.key)"
			>
				<input
					class="min-w-0 flex-1 rounded-4 bg-transparent px-1 py-0.5 text-sm text-ink-gray-8 hover:bg-surface-gray-2 focus:bg-surface-gray-2"
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
				<Button label="Reset" :loading="busy" :disabled="loading" @click="reset" />
				<Button
					variant="solid"
					label="Save"
					:loading="busy"
					:disabled="loading || !!failed"
					@click="save"
				/>
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
import { Button, Dialog, Skeleton } from "frappe-ui";
import type { Navigation } from "@/boot";
import LoadingStatus from "./LoadingStatus.vue";
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
// `loading` is the list's first read; `busy` is Reset's or Save's own request.
const loading = ref(false);
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
		loading.value = false;
		busy.value = false;
		failed.value = null;
		dragging.value = null;
		if (target) load(target);
	},
	{ immediate: true }
);

async function load(target: Address) {
	const mine = generation;
	loading.value = true;
	await read(target, mine);
	if (mine === generation) loading.value = false;
}

async function read(target: Address, mine: number) {
	try {
		const rows = await fetchArrangement(target);
		if (mine === generation) items.value = rows;
	} catch (error) {
		if (mine === generation)
			failed.value = `Could not load this list: ${(error as Error).message}`;
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
	const target = props.target;
	if (target) await hold((mine) => write(saveArrangement(target, items.value), mine));
}

async function reset() {
	const target = props.target;
	if (!target) return;
	await hold(async (mine) => {
		await write(resetArrangement(target), mine);
		await read(target, mine);
	});
}

/** Spins Reset and Save for one action of theirs, unless a new target has taken over. */
async function hold(action: (mine: number) => Promise<void>) {
	const mine = generation;
	busy.value = true;
	await action(mine);
	if (mine === generation) busy.value = false;
}

async function write(request: Promise<Navigation>, mine: number) {
	try {
		emit("saved", await request);
	} catch (error) {
		if (mine === generation)
			failed.value = `Could not save this list: ${(error as Error).message}`;
	}
}
</script>
