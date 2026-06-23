<script setup>
import { ref, computed, watch, nextTick } from "vue";
import PanelDropdown from "./PanelDropdown.vue";
import { Button, FeatherIcon } from "@/lib/ui";
import { useStore } from "@/store";
import { __ } from "@/lib/translate";

const {
	agents,
	models,
	selectedAgent,
	selectedModel,
	sending,
	paused,
	locked,
	needsSetup,
	focusTick,
	agentLabel,
	modelLabel,
	setAgent,
	setModel,
	send,
} = useStore();

const text = ref("");
const el = ref(null);

const agentItems = computed(() => agents.value.map((a) => ({ value: a.name, label: a.title })));
const modelItems = computed(() => [
	{ value: null, label: __("Default") },
	...models.value.map((m) => ({ value: m.name, label: m.title })),
]);

const canSend = computed(
	() => text.value.trim() && !sending.value && !paused.value && !needsSetup.value
);
const placeholder = computed(() =>
	needsSetup.value ? __("Setup required…") : __("Ask {0}…", [agentLabel(selectedAgent.value)])
);

function submit() {
	if (!canSend.value) return;
	send(text.value);
	text.value = "";
	resize();
}

function onKeydown(e) {
	if (e.key === "Enter" && !e.shiftKey) {
		e.preventDefault();
		submit();
	}
}

function resize() {
	const t = el.value;
	if (!t) return;
	t.style.height = "auto";
	t.style.height = `${Math.min(t.scrollHeight, 160)}px`;
}

watch(focusTick, () => nextTick(() => el.value?.focus()));
</script>

<template>
	<div class="border-t border-outline-gray-1 px-4 pb-3.5 pt-2.5">
		<div
			class="flow-composer flex flex-col gap-1.5 rounded-xl border border-outline-gray-2 bg-surface-white px-2.5 py-2 shadow-sm"
		>
			<textarea
				ref="el"
				v-model="text"
				rows="1"
				:placeholder="placeholder"
				:disabled="sending || paused || needsSetup"
				class="max-h-40 min-h-[22px] w-full resize-none border-0 bg-transparent text-base leading-relaxed text-ink-gray-9 outline-none placeholder:text-ink-gray-4"
				@keydown="onKeydown"
				@input="resize"
			></textarea>

			<div class="flex items-center gap-1.5">
				<!-- agent -->
				<PanelDropdown
					:items="agentItems"
					:model-value="selectedAgent"
					:disabled="locked"
					@update:model-value="setAgent"
				>
					<template #trigger="{ toggle }">
						<button
							class="flex h-6 items-center gap-1 rounded px-1.5 text-[11.5px] text-ink-gray-6 hover:bg-surface-gray-2 disabled:cursor-default disabled:hover:bg-transparent"
							:disabled="locked"
							:title="__('Agent')"
							@click="toggle"
						>
							<span class="h-1.5 w-1.5 rounded-full bg-surface-green-3"></span>
							<span class="font-medium text-ink-gray-8">{{
								agentLabel(selectedAgent)
							}}</span>
							<FeatherIcon v-if="!locked" name="chevron-down" class="h-3 w-3" />
						</button>
					</template>
				</PanelDropdown>

				<span class="text-ink-gray-3">/</span>

				<!-- model -->
				<PanelDropdown
					:items="modelItems"
					:model-value="selectedModel"
					@update:model-value="setModel"
				>
					<template #trigger="{ toggle }">
						<button
							class="flex h-6 items-center gap-1 rounded px-1.5 text-[11.5px] text-ink-gray-6 hover:bg-surface-gray-2"
							:title="__('Model')"
							@click="toggle"
						>
							<span class="font-medium text-ink-gray-8">
								{{ modelLabel(selectedModel) || __("Default") }}
							</span>
							<FeatherIcon name="chevron-down" class="h-3 w-3" />
						</button>
					</template>
				</PanelDropdown>

				<span class="flex-1"></span>

				<Button variant="solid" :disabled="!canSend" :title="__('Send')" @click="submit">
					<template #icon><FeatherIcon name="arrow-up" class="h-4 w-4" /></template>
				</Button>
			</div>
		</div>
	</div>
</template>
