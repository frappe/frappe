<script setup>
import { computed } from "vue";
import { FeatherIcon } from "@/lib/ui";
import { __ } from "@/lib/translate";

const props = defineProps({
	part: { type: Object, required: true },
	awaitingApproval: Boolean,
});

const status = computed(() => {
	if (props.awaitingApproval) return { label: __("Needs approval"), tone: "warn" };
	if (props.part.approval === "denied") return { label: __("Denied"), tone: "muted" };
	if (props.part.approval === "redirected")
		return { label: __("Changes requested"), tone: "muted" };
	if (props.part.result !== null) return { label: __("Done"), tone: "muted" };
	return { label: __("Running"), tone: "muted" };
});

const showOutput = computed(
	() => props.part.result !== null && props.part.result !== "" && !props.awaitingApproval
);

// Format lazily — only when the card is open — so a stream of tool calls never
// pays the JSON.stringify cost up front.
const input = computed(() => (props.part.expanded ? formatArgs(props.part.arguments) : ""));
const output = computed(() =>
	props.part.expanded && showOutput.value ? formatResult(props.part.result) : ""
);

function toggle() {
	props.part.expanded = !props.part.expanded;
}

function formatArgs(args) {
	if (!args) return "";
	try {
		const obj = typeof args === "string" ? JSON.parse(args) : args;
		return JSON.stringify(obj, null, 2);
	} catch {
		return typeof args === "string" ? args : String(args);
	}
}

function formatResult(result) {
	if (result == null) return "";
	try {
		return JSON.stringify(JSON.parse(result), null, 2);
	} catch {
		return String(result);
	}
}
</script>

<template>
	<div class="overflow-hidden rounded-lg border border-outline-gray-1 bg-surface-white">
		<button
			class="flex w-full items-center gap-2 px-3 py-2.5 text-left transition-colors hover:bg-surface-gray-1"
			@click="toggle"
		>
			<FeatherIcon
				name="chevron-right"
				class="h-3.5 w-3.5 shrink-0 text-ink-gray-5 transition-transform"
				:class="{ 'rotate-90': part.expanded }"
			/>
			<span class="text-sm text-ink-gray-8">{{ part.name }}</span>
			<span class="flex-1"></span>
			<span
				class="shrink-0 text-xs"
				:class="status.tone === 'warn' ? 'tc-warn' : 'text-ink-gray-5'"
			>
				{{ status.label }}
			</span>
		</button>

		<div v-if="part.expanded" class="border-t border-outline-gray-1 px-3 py-2.5">
			<div class="mb-1 text-[10.5px] font-semibold uppercase tracking-wide text-ink-gray-5">
				{{ __("Input") }}
			</div>
			<pre class="flow-code">{{ input }}</pre>

			<template v-if="showOutput">
				<div
					class="mb-1 mt-3 text-[10.5px] font-semibold uppercase tracking-wide text-ink-gray-5"
				>
					{{ __("Output") }}
				</div>
				<pre class="flow-code">{{ output }}</pre>
			</template>
		</div>
	</div>
</template>

<style scoped>
.tc-warn {
	color: var(--ink-amber-3, var(--orange-500, #c2780c));
	font-weight: var(--weight-medium, 500);
}
.flow-code {
	margin: 0;
	max-height: 320px;
	overflow: auto;
	white-space: pre-wrap;
	word-break: break-word;
	border-radius: 6px;
	border: 1px solid var(--outline-gray-1);
	background: var(--surface-gray-1);
	padding: 8px 10px;
	font-family: var(--font-stack-monospace, ui-monospace, monospace);
	font-size: 11.5px;
	line-height: 1.55;
	color: var(--ink-gray-8);
}
</style>
