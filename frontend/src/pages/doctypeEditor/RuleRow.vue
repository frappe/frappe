<!-- One rule as one line in words, its sentence in a Tooltip. The dialog it opens edits a draft and
     stages it once, as it closes, so a session is one undo step. -->
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
		<Dialog
			v-if="draft"
			:open="open"
			:title="[label, subject].filter(Boolean).join(' · ')"
			size="2xl"
			@update:open="!$event && close()"
			@after-leave="button?.focus()"
		>
			<component
				:is="editor"
				:draft="draft"
				:note="note"
				:fields="fields"
				:referable="referable"
				:filters="filters"
				@done="close"
			/>
		</Dialog>
	</PanelRow>
</template>

<script lang="ts">
// Rows share the builder's load: only the row clicked last opens when it arrives.
let lastOpened: symbol | undefined;
</script>

<script setup lang="ts">
import { onBeforeUnmount, ref, shallowRef } from "vue";
import { Dialog, Tooltip } from "frappe-ui";
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

const button = ref<HTMLButtonElement | null>(null);
const open = ref(false);
const draft = shallowRef<RuleDraft | null>(null);
// The builder loads as a rule first opens, not with the editor page.
const editor = shallowRef<typeof import("./RuleEditor.vue").default>();

async function toggle() {
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
	open.value = true;
}

function close() {
	finish();
}

function finish() {
	if (!open.value) return;
	open.value = false;
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
</script>
