<template>
	<!-- the skills a new chat's agent can load, beside the composer's + menu -->
	<PalettePanel
		title="Skills"
		dropdown
		align="left"
		:beside="beside"
		:query="search"
		@close="emit('close')"
	>
		<!-- nothing to search before there is a skill -->
		<div v-if="skills.length" class="flex flex-none pl-1 pr-2.5 pt-1">
			<input
				ref="field"
				v-model="search"
				placeholder="Search skills…"
				class="h-8 min-w-0 flex-1 border-0 bg-transparent px-[11px] text-base text-ink-gray-9 outline-none placeholder:text-ink-gray-4 focus:ring-0"
			/>
		</div>
		<div class="flow-palette-list min-h-0 flex-1 overflow-y-auto p-1">
			<button
				v-for="skill in options"
				:key="skill.name"
				data-palette-item
				class="flow-palette-row"
				@click="emit('pick', `/skill:${skill.name} `)"
			>
				<span class="max-w-[40%] flex-none truncate">{{ skill.name }}</span>
				<span class="flow-palette-hint min-w-0 flex-1 truncate">
					{{ skill.description }}
				</span>
			</button>
			<div v-if="!options.length" class="flow-palette-empty">
				{{ skills.length ? "No matching skills" : "No skills" }}
			</div>
			<!-- with none, or none found: the way to a new one -->
			<button
				v-if="canAdd && !options.length"
				data-palette-item
				class="flow-palette-row"
				@click="create"
			>
				<span class="lucide-plus size-4 flex-none" aria-hidden="true" />
				Add a skill
			</button>
		</div>
	</PalettePanel>
</template>

<script setup>
import { computed, inject, onMounted, ref } from "vue";
import PalettePanel from "@flow/ui-core/components/PalettePanel.vue";
import { layout } from "@flow/ui-core/layout.js";

// The skills a new chat's agent can load, beside the composer's + menu; a pick puts it in the
// draft. Shown without any too, for someone who may add one.
defineProps({ beside: { type: Number, default: 0 } }); // this far from the + button's left
// pick: "/skill:<name> ", for the composer to put in the draft
const emit = defineEmits(["pick", "close"]);
const flow = inject("flow");
const page = inject("flowPage");
const search = ref("");
const field = ref(null);

const skills = computed(() => flow.state.skills ?? []);
const canAdd = computed(() => page.can("Flow Skill", "create"));
// matched by every word of the search in their name or description
const options = computed(() => {
	const words = search.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
	return skills.value.filter((skill) => {
		const text = `${skill.name} ${skill.description ?? ""}`.toLowerCase();
		return words.every((word) => text.includes(word));
	});
});
// a phone's list leaves its search for a tap, rather than raise the keyboard over it
onMounted(() => layout.phone || field.value?.focus());

// settings, on a blank skill; the dialog takes the focus, so the closing menu gives it to no one
function create() {
	emit("close", false);
	page.createRecord("skills");
	flow.setSettingsOpen(true);
}
</script>
