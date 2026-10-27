<!-- Arrange mode: every app in a drag grid with an eye to hide it, under a strip with Reset and Done. -->
<template>
	<div
		class="mt-6 flex w-full flex-wrap items-center justify-end gap-x-3 gap-y-2 rounded-5 bg-surface-gray-2 py-2 pl-3 pr-2"
		:class="boxWidthClass"
		data-arrange-strip
	>
		<span class="flex-auto text-sm text-ink-gray-7">
			{{ __("Drag to reorder. Click the eye to hide an app.") }}
		</span>
		<div class="flex shrink-0 gap-2">
			<Button :label="__('Reset')" variant="ghost" :disabled="saving" @click="reset" />
			<Button :label="__('Done')" variant="solid" :loading="saving" @click="done" />
		</div>
	</div>

	<Draggable
		v-model="draft"
		item-key="app"
		tag="ul"
		:aria-label="__('Apps')"
		class="mt-8 grid gap-x-4 gap-y-6"
		:class="gridClass(draft.length)"
		:animation="150"
		:disabled="saving"
	>
		<template #item="{ element: app }">
			<li class="relative cursor-grab active:cursor-grabbing" :data-app="app.app">
				<div
					class="flex flex-col items-center gap-2 rounded-5 p-2 transition"
					:class="{ 'opacity-35': app.hidden }"
				>
					<AppLogo :logo="app.logo" :title="app.title" />
					<span class="line-clamp-2 text-center text-sm leading-snug text-ink-gray-8">
						{{ app.title }}
					</span>
				</div>
				<button
					type="button"
					class="absolute right-3 top-1 flex size-6 items-center justify-center rounded-full bg-surface-white text-ink-gray-7 shadow ring-1 ring-outline-gray-2 transition hover:bg-surface-gray-2 focus-visible:focus-ring"
					:aria-label="__('Hide {0}', [app.title])"
					:aria-pressed="app.hidden"
					aria-keyshortcuts="Alt+ArrowLeft Alt+ArrowRight"
					data-eye
					@click="toggle(app)"
					@keydown.alt.left.prevent="move(app, -1)"
					@keydown.alt.right.prevent="move(app, 1)"
				>
					<span
						class="size-3.5"
						:class="app.hidden ? 'lucide-eye' : 'lucide-eye-off'"
						aria-hidden="true"
					/>
				</button>
			</li>
		</template>
	</Draggable>
</template>

<script setup lang="ts">
import { nextTick, ref } from "vue";
import { Button, toast } from "frappe-ui";
// @ts-ignore, vuedraggable ships no bundled types
import Draggable from "vuedraggable";
import { __ } from "@/i18n";
import type { IndexApp } from "./apps";
import AppLogo from "./AppLogo.vue";
import { gridClass } from "./grid";
import { resetLayer, saveLayer } from "./layer";

const props = defineProps<{ apps: IndexApp[]; boxWidthClass: string }>();
const emit = defineEmits<{ done: [apps: IndexApp[]] }>();

const draft = ref<IndexApp[]>([...props.apps]);
const saving = ref(false);

function toggle(app: IndexApp) {
	draft.value = draft.value.map((entry) =>
		entry.app === app.app ? { ...entry, hidden: !entry.hidden } : entry
	);
}

// Moving the focused node out and back in blurs it, so the eye takes focus again.
async function move(app: IndexApp, by: -1 | 1) {
	const from = draft.value.findIndex((entry) => entry.app === app.app);
	const to = from + by;
	if (to < 0 || to >= draft.value.length) return;

	const moved = [...draft.value];
	[moved[from], moved[to]] = [moved[to], moved[from]];
	draft.value = moved;
	await nextTick();
	document.querySelector<HTMLElement>(`li[data-app="${app.app}"] [data-eye]`)?.focus();
}

async function reset() {
	const apps = await write(resetLayer);
	if (apps) draft.value = apps;
}

async function done() {
	const apps = await write(() => saveLayer(draft.value));
	if (apps) emit("done", apps);
}

async function write(save: () => Promise<IndexApp[]>): Promise<IndexApp[] | undefined> {
	saving.value = true;
	try {
		return await save();
	} catch (error) {
		toast.error(__("Could not save your apps: {0}", [(error as Error).message]));
	} finally {
		saving.value = false;
	}
}
</script>
