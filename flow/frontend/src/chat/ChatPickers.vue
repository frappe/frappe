<template>
	<!-- a new chat's agent and skills, beside the composer's +; once it starts, the agent is kept and
	     skills are in the + menu -->
	<span class="relative flex-none">
		<Tooltip :text="open === 'agent' ? '' : `Agent: ${agentTitle}`">
			<button
				ref="agentButton"
				type="button"
				:class="[BUTTON, tall ? 'h-8 w-8' : 'h-7 w-7', open === 'agent' && 'bg-surface-gray-2']"
				:aria-label="`Agent: ${agentTitle}`"
				:aria-expanded="open === 'agent'"
				@click="toggle('agent')"
			>
				<span class="lucide-bot size-4" aria-hidden="true" />
			</button>
		</Tooltip>
		<AgentPicker v-if="open === 'agent'" @close="close" />
	</span>
	<span v-if="hasSkills" class="relative flex-none">
		<Tooltip :text="open === 'skills' ? '' : 'Skills'">
			<button
				ref="skillsButton"
				type="button"
				:class="[BUTTON, tall ? 'h-8 w-8' : 'h-7 w-7', open === 'skills' && 'bg-surface-gray-2']"
				aria-label="Skills"
				:aria-expanded="open === 'skills'"
				@click="toggle('skills')"
			>
				<span class="lucide-book-open size-4" aria-hidden="true" />
			</button>
		</Tooltip>
		<SkillPicker v-if="open === 'skills'" @close="close" @pick="pick" />
	</span>
</template>

<script setup>
import { computed, inject, nextTick, ref } from "vue";
import { Tooltip } from "frappe-ui";

import { useAgent } from "./agent.js";
import AgentPicker from "./AgentPicker.vue";
import SkillPicker from "./SkillPicker.vue";

// `insert` puts a picked skill in the draft, as the composer's "/" list does; `tall` as its + button
const props = defineProps({
	insert: { type: Function, required: true },
	tall: { type: Boolean, default: false },
});
const flow = inject("flow");
const page = inject("flowPage");
const { current } = useAgent();

const open = ref(null); // "agent" | "skills"
const agentButton = ref(null);
const skillsButton = ref(null);
const agentTitle = computed(
	() => page.state.boot.agents.find((agent) => agent.name === current.value)?.title ?? "Agent"
);
// skills where there are some, or one can be added
const hasSkills = computed(() => (flow.state.skills ?? []).length > 0 || page.can("Flow Skill", "create"));

function toggle(name) {
	open.value = open.value === name ? null : name;
}

// closed, focus goes back to the button that opened it, unless something else takes it
function close(refocus = true) {
	const button = open.value === "agent" ? agentButton : skillsButton;
	open.value = null;
	if (refocus !== false) nextTick(() => button.value?.focus());
}

function pick(word) {
	close(false);
	props.insert(word);
}

// the composer's + button, matched
const BUTTON =
	"grid flex-none place-items-center rounded-5 text-ink-gray-6 hover:bg-surface-gray-2 hover:text-ink-gray-9 dark:text-ink-gray-8";
</script>
