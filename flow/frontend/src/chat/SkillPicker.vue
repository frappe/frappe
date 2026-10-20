<template>
	<span v-if="skills.length || canAdd" class="min-w-0 sm:relative">
		<!-- its list hangs from it, but on a phone from the whole row, which spans the box -->
		<button
			ref="trigger"
			class="flex max-w-full items-center gap-1.5 rounded-4 px-1.5 py-1 hover:bg-surface-gray-2 hover:text-ink-gray-8"
			:class="open ? 'bg-surface-gray-2' : ''"
			title="Skills"
			:aria-expanded="open"
			:disabled="disabled"
			@click="open ? close() : show()"
		>
			<FeatherIcon name="book-open" class="h-3.5 w-3.5 flex-none" />
			<span class="truncate">Skills</span>
			<FeatherIcon
				name="chevron-down"
				class="h-3 w-3 flex-none text-ink-gray-4 transition-transform dark:text-ink-gray-6"
				:class="open ? 'rotate-180' : ''"
			/>
		</button>
		<PalettePanel
			v-if="open"
			title="Skills"
			dropdown
			align="left"
			:query="search"
			@close="close"
		>
			<!-- nothing to search before there is a skill -->
			<div v-if="skills.length" class="flex flex-none pl-1 pr-2.5 pt-1">
				<input
					ref="field"
					v-model="search"
					placeholder="Search skills…"
					class="h-8 min-w-0 flex-1 border-0 bg-transparent px-[11px] text-sm text-ink-gray-9 outline-none placeholder:text-ink-gray-4 focus:ring-0"
				/>
			</div>
			<div class="flow-palette-list min-h-0 flex-1 overflow-y-auto p-1">
				<button
					v-for="skill in options"
					:key="skill.name"
					data-palette-item
					class="flow-palette-row"
					@click="pick(skill.name)"
				>
					<span class="max-w-[40%] flex-none truncate">{{ skill.name }}</span>
					<span class="flow-palette-hint min-w-0 flex-1 truncate">
						{{ skill.description }}
					</span>
				</button>
				<div v-if="!options.length" class="flow-palette-empty">
					{{ skills.length ? "No matching skills" : "No skills" }}
				</div>
				<button v-if="canAdd" data-palette-item class="flow-palette-row" @click="create">
					<FeatherIcon name="plus" class="h-4 w-4 flex-none" />
					Add a skill
				</button>
			</div>
		</PalettePanel>
	</span>
</template>

<script setup>
import { computed, inject, nextTick, onMounted, ref } from "vue";
import FeatherIcon from "@flow/ui-core/components/FeatherIcon.vue";
import PalettePanel from "@flow/ui-core/components/PalettePanel.vue";

// The skills a new chat's agent can load, over the composer; a pick starts the draft with it.
// Shown without any too, for someone who may add one.
defineProps({ disabled: { type: Boolean, default: false } });
const emit = defineEmits(["pick"]); // "/skill:<name> ", for the composer to put in the draft
const flow = inject("flow");
const page = inject("flowPage");
const open = ref(false);
const search = ref("");
const trigger = ref(null);
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
// listed before anything is typed; the page reloads them when the agent changes
onMounted(() => void flow.loadSkills());

function show() {
	search.value = "";
	open.value = true;
	nextTick(() => field.value?.focus());
}

function close() {
	open.value = false;
	nextTick(() => trigger.value?.focus());
}

// the draft takes the focus
function pick(name) {
	open.value = false;
	emit("pick", `/skill:${name} `);
}

// settings, on a blank skill; the dialog takes the focus
function create() {
	open.value = false;
	page.createRecord("skills");
	flow.setSettingsOpen(true);
}
</script>
