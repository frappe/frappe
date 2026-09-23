<!-- The open writer, docked in its record's band or floating over the shell across pages. -->
<template>
	<div ref="shellSlot" class="contents" data-composer-slot />
	<Teleport v-if="target && writer" :to="target">
		<FloatingWindow
			:key="recordKey"
			v-model:mode="mode"
			:minimizable="false"
			:storageKey="floatKey"
			class="pointer-events-auto border border-outline-gray-2"
			:class="{ 'shadow-lg': docked, 'select-none': dock.dragging.value }"
			:style="docked ? { height: `${dock.height.value}px` } : undefined"
			data-composer-card
			data-composer-window
		>
			<template #header="{ float }">
				<button
					v-if="docked"
					type="button"
					class="absolute left-1/2 top-0 z-10 flex h-3 w-24 -translate-x-1/2 cursor-ns-resize touch-none items-center justify-center opacity-60 hover:opacity-100"
					:aria-label="__('Resize the composer')"
					data-composer-handle
					@pointerdown="resize"
					@pointermove="dock.move"
					@pointerup="dock.end"
					@pointercancel="dock.end"
				>
					<span class="h-1 w-10 rounded-full bg-surface-gray-4" />
				</button>
				<div class="flex shrink-0 items-center gap-2 px-3 pt-3">
					<span
						v-if="writer.icon"
						class="size-4 shrink-0 text-ink-gray-5"
						:class="writer.icon"
						aria-hidden="true"
					/>
					<span
						class="truncate text-base font-medium text-ink-gray-8"
						data-composer-title
					>
						{{ `${writer.label} · ${context.title}` }}
					</span>
					<div class="ml-auto flex shrink-0">
						<Tooltip v-if="docked" :text="__('Pop out')">
							<Button
								icon="lucide-maximize-2"
								variant="ghost"
								:label="__('Pop out')"
								data-composer-float
								@click="place('floating', float)"
							/>
						</Tooltip>
						<Tooltip v-else-if="composerDock()" :text="__('Dock')">
							<Button
								icon="lucide-minimize-2"
								variant="ghost"
								:label="__('Dock')"
								data-composer-dock-button
								@click="place('docked')"
							/>
						</Tooltip>
						<Tooltip :text="__('Collapse')">
							<Button
								icon="lucide-chevrons-down-up"
								variant="ghost"
								:label="__('Collapse')"
								data-composer-collapse
								@click="closeComposer()"
							/>
						</Tooltip>
					</div>
				</div>
			</template>

			<div class="flex h-full min-h-0 flex-col">
				<component
					:is="writer.component"
					v-if="writer.component"
					v-bind="{ ...writer.props, page: context.page, close: closeComposer }"
				/>
				<CommentWriter
					v-else-if="writer.name === COMMENT_WRITER"
					:key="commentRevision"
					:context="context"
					:user="user"
				/>
				<EmailWriter
					v-else-if="writer.name === EMAIL_WRITER"
					:key="emailRevision"
					:context="context"
					:user="user"
				/>
			</div>
		</FloatingWindow>
	</Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Button, Tooltip } from "frappe-ui";
import { FloatingWindow } from "frappe-ui/experimental";
import type { SessionUser } from "@framework/ui/api";
import { __ } from "@/i18n";
import { COMMENT_WRITER } from "@/pages/record/composer/commentDraft";
import CommentWriter from "@/pages/record/composer/CommentWriter.vue";
import { EMAIL_WRITER } from "@/pages/record/composer/emailDraft";
import EmailWriter from "@/pages/record/composer/EmailWriter.vue";
import { useDockHeight } from "@/pages/record/composer/useDockHeight";
import { openWriterContext, openWriterItems } from "@/pages/record/composer/writerContext";
import {
	closeComposer,
	composerDock,
	composerState,
	composerUser,
	draftRevision,
	setComposerWindow,
	type ComposerWindow,
} from "./composer";

defineProps<{ user: SessionUser }>();

const shellSlot = ref<HTMLElement | null>(null);
// The store's user, so every key the composer keeps belongs to one reader.
const reader = composerUser();
const dock = useDockHeight(reader);
const floatKey = `desk:composer-float:${reader}`;

const docked = computed(() => composerState.window === "docked");
const target = computed(() => (docked.value ? composerDock() : shellSlot.value));
const recordKey = computed(() => JSON.stringify([composerState.doctype, composerState.name]));
const context = computed(openWriterContext);
// Away from its record a script's writer has no page to take, so it waits for the record.
const writer = computed(() => {
	const open = composerState.active;
	const item = open ? openWriterItems().find((one) => one.name === open) : undefined;
	return item?.component && !context.value.page ? undefined : item;
});
// A draft set from outside the writer, as a failed post does, draws in a fresh editor.
const commentRevision = computed(() =>
	draftRevision(composerState.doctype, composerState.name, COMMENT_WRITER)
);
const emailRevision = computed(() =>
	draftRevision(composerState.doctype, composerState.name, EMAIL_WRITER)
);

// The window's own changes; the header's controls move the card and keep the choice.
const mode = computed({
	get: () => composerState.window,
	set: (value: string) => {
		if (value === "docked" || value === "floating") setComposerWindow(value);
	},
});

// The window takes its place from storage when it mounts; the store's, maybe one open's, must win.
watch(() => (target.value && writer.value ? recordKey.value : ""), storeWindow, {
	immediate: true,
});

function storeWindow(shown: string) {
	if (!shown) return;
	const kept = storedFloat();
	try {
		if (kept?.rect)
			localStorage.setItem(
				floatKey,
				JSON.stringify({ rect: onScreen(kept.rect), mode: composerState.window })
			);
		// With no rectangle the window starts from `v-model`; a partial entry would break it.
		else localStorage.removeItem(floatKey);
	} catch {
		// Storage can be full or refused; the window then takes its stored place.
	}
}

function storedFloat() {
	try {
		return JSON.parse(localStorage.getItem(floatKey) ?? "null");
	} catch {
		return null;
	}
}

// A browser window that shrank since the rectangle was kept would mount the card off screen.
function onScreen(rect: { x: number; y: number; width: number; height: number }) {
	const width = Math.min(rect.width, innerWidth);
	const height = Math.min(rect.height, innerHeight);
	return {
		x: clamp(rect.x, 0, innerWidth - width),
		y: clamp(rect.y, 0, innerHeight - height),
		width,
		height,
	};
}

function clamp(value: number, min: number, max: number) {
	return Math.min(Math.max(value, min), Math.max(max, min));
}

// `float` pulls a kept rectangle back inside a window that has shrunk since.
function place(placement: ComposerWindow, float?: () => void) {
	float?.();
	setComposerWindow(placement, { remember: true });
}

function resize(event: PointerEvent) {
	const card = (event.currentTarget as HTMLElement).closest<HTMLElement>(
		"[data-composer-window]"
	);
	dock.begin(event, card?.offsetHeight ?? dock.height.value);
}
</script>
