<!-- One rule as one line in words, its sentence in a Tooltip. The popover below the row edits a draft
     and stages it once, as it closes, so a session is one undo step. -->
<template>
	<PanelRow :label="label" :box="false">
		<Tooltip :disabled="!sentence || open">
			<template #content>
				<p class="max-w-[320px] whitespace-normal break-words">{{ sentence }}</p>
			</template>
			<button
				ref="button"
				type="button"
				class="flex h-7 w-full min-w-0 items-center gap-1.5 rounded-4 px-2 text-left disabled:cursor-not-allowed"
				:class="open ? 'bg-surface-gray-3' : 'enabled:hover:bg-surface-gray-2'"
				:disabled="disabled"
				:aria-expanded="open"
				:data-rule-row="rowKey"
				@click="toggle"
			>
				<span
					v-if="summary.kind === 'code'"
					class="lucide-code size-4 shrink-0 text-ink-gray-5"
					aria-hidden="true"
				/>
				<span class="min-w-0 flex-1 truncate" :class="TEXT[summary.kind]">
					{{ summary.text }}
				</span>
				<span
					class="lucide-chevron-down size-4 shrink-0 text-ink-gray-5"
					aria-hidden="true"
				/>
			</button>
		</Tooltip>
		<slot />
		<Popover
			v-if="button && draft"
			:open="open"
			trigger="manual"
			:reference="button"
			side="bottom"
			align="end"
			@update:open="onPopover"
		>
			<!-- Capped at the room under the row, so a growing builder scrolls instead of flipping above it. -->
			<div
				class="w-[600px] overflow-y-auto"
				style="max-height: var(--reka-popover-content-available-height)"
				@keydown.esc.stop="close"
			>
				<component
					:is="editor"
					:draft="draft"
					:title="label"
					:subject="subject"
					:note="note"
					:fields="fields"
					:referable="referable"
					:filters="filters"
					@done="close"
				/>
			</div>
		</Popover>
	</PanelRow>
</template>

<script lang="ts">
// Rows share the builder's load: only the row clicked last opens when it arrives.
let lastOpened: symbol | undefined;
</script>

<script setup lang="ts">
import { onBeforeUnmount, ref, shallowRef } from "vue";
import { Popover, Tooltip } from "frappe-ui";
import type { ConditionField } from "@framework/ui/ConditionBuilder";
import PanelRow from "./PanelRow.vue";
import { RuleDraft, type RuleCodec } from "./ruleDraft";
import type { RuleSummary } from "./ruleWords";

const props = defineProps<{
	label: string;
	value: string;
	summary: RuleSummary;
	/** The Tooltip's full sentence; empty for no rule. */
	sentence: string;
	subject: string;
	note: string;
	rowKey: string;
	codec: RuleCodec;
	fields: ConditionField[];
	referable: ConditionField[];
	/** Stages the edited value; bound to the field or container the row was drawn for. */
	commit: (value: string) => void;
	filters?: boolean;
	disabled?: boolean;
}>();

const TEXT = {
	empty: "text-base text-ink-gray-5",
	rules: "text-base text-ink-gray-8",
	code: "font-mono text-sm text-ink-gray-7",
};
const PANEL_ROOM = 560;

const button = ref<HTMLButtonElement | null>(null);
const open = ref(false);
const draft = shallowRef<RuleDraft | null>(null);
// The builder loads as a rule first opens, not with the editor page; an empty popover would close on focus.
const editor = shallowRef<typeof import("./RuleEditor.vue").default>();

// The popover closes on a click outside, which the row's own button is; that click must not reopen it.
let closedAt = 0;
let release = () => {};

async function toggle() {
	if (Date.now() - closedAt < 300) return;
	if (open.value) return close();
	const request = (lastOpened = Symbol());
	const stop = onDismiss(() => lastOpened === request && (lastOpened = undefined));
	try {
		editor.value ??= (await import("./RuleEditor.vue")).default;
	} finally {
		stop();
	}
	if (open.value || request !== lastOpened) return; // a later click, outside click or Escape during the load wins
	draft.value = new RuleDraft(props.value, props.codec);
	release = makeRoomBelow(button.value, PANEL_ROOM);
	open.value = true;
}

function onPopover(next: boolean) {
	if (next) return;
	finish();
	closedAt = Date.now();
}

function close() {
	finish();
	button.value?.focus();
}

function finish() {
	if (!open.value) return;
	open.value = false;
	release();
	release = () => {};
	if (draft.value?.changed()) props.commit(draft.value.value.value);
}

onBeforeUnmount(finish);

/** Calls `cancel` on a click outside the row or on Escape; returns the stop. */
function onDismiss(cancel: () => void) {
	const onPointer = (e: Event) => button.value?.contains(e.target as Node) || cancel();
	const onKey = (e: KeyboardEvent) => e.key === "Escape" && cancel();
	document.addEventListener("pointerdown", onPointer, true);
	document.addEventListener("keydown", onKey, true);
	return () => {
		document.removeEventListener("pointerdown", onPointer, true);
		document.removeEventListener("keydown", onKey, true);
	};
}

/** A row near the panel's foot would flip the popover above it: scroll the row up, padding the panel's end. */
function makeRoomBelow(el: HTMLElement | null, need: number) {
	const panel = el?.closest<HTMLElement>("[data-editor-panel]");
	if (!el || !panel) return () => {};
	const room = window.innerHeight - el.getBoundingClientRect().bottom - 16;
	if (room >= need) return () => {};
	panel.style.paddingBottom = `${need}px`;
	panel.scrollBy({ top: need - room });
	return () => (panel.style.paddingBottom = "");
}
</script>
