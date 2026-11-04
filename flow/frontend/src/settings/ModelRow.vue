<template>
	<!-- a model as a card of its own: its name (which opens its details) and state, its id under
	     them, and its switch at the right -->
	<li class="flex min-w-0 flex-col gap-1 rounded-6 border border-outline-gray-2 px-4 py-3">
		<div class="flex min-w-0 items-center gap-3">
			<div class="flex min-w-0 flex-1 flex-col gap-0.5">
				<div class="flex min-w-0 items-center gap-2">
					<button
						type="button"
						class="min-w-0 truncate text-left text-base text-ink-gray-9 hover:underline hover:decoration-outline-gray-4 hover:underline-offset-4 disabled:hover:no-underline"
						:disabled="model.adding"
						:title="`${model.title} details`"
						@click="emit('open')"
					>
						{{ model.title }}
					</button>
					<!-- one badge, always the same height, saying where it stands: it is Active only once the
					     check says so -->
					<Badge v-if="model.adding" label="Adding…" theme="gray" class="flex-none" />
					<Badge v-else-if="checking" label="Checking…" theme="gray" class="flex-none" />
					<Badge v-else-if="failed" label="Not working" theme="red" class="flex-none" />
					<Badge v-else-if="paused || !model.enabled" label="Off" theme="gray" class="flex-none" />
					<Badge v-else label="Active" theme="green" class="flex-none" />
				</div>
				<span v-if="subtitle" class="truncate text-base text-ink-gray-5" :title="subtitle">{{ subtitle }}</span>
			</div>
			<Switch
				:model-value="Boolean(model.enabled) && !paused"
				:disabled="!canWrite || checking || model.adding || paused"
				:aria-label="`${model.title} on`"
				class="flex-none"
				@update:model-value="(on) => emit('toggle', on)"
			/>
		</div>
		<!-- one that didn't answer says why, where it is, and what can be done -->
		<div v-if="failed && !checking" class="flex flex-wrap items-center gap-x-3 gap-y-1 pt-1 text-sm">
			<span class="min-w-0 text-ink-red-6" :title="model.check.message">{{ reason }}</span>
			<!-- a key it refused needs a new key, not another try -->
			<button v-if="rekey && model.check.reason === 'wrong_key'" type="button" :class="QUIET" @click="emit('rekey')">
				Change key
			</button>
			<button v-else-if="canWrite" type="button" :class="QUIET" @click="emit('retry')">Try again</button>
			<button v-if="canDelete" type="button" :class="QUIET" @click="emit('remove')">Remove</button>
		</div>
	</li>
</template>

<script setup>
import { computed } from "vue";
import { Badge, Switch } from "frappe-ui";

// A model on the Models tab: a switch labelled with its name, what its last check said, and a menu
// for the rest (its form, a check, removing it). Only an exception stays: a model that answers
// shows "Works" just after it was checked.
const props = defineProps({
	model: { type: Object, required: true },
	note: { type: String, default: "" }, // "Recommended", or the id of a model without a service
	checking: { type: Boolean, default: false },
	passed: { type: Boolean, default: false }, // checked just now, and it answered
	canWrite: { type: Boolean, default: false },
	canDelete: { type: Boolean, default: false },
	rekey: { type: Boolean, default: false }, // its service's key can be changed from here
	subtitle: { type: String, default: "" }, // where it comes from, under its name
	paused: { type: Boolean, default: false }, // its provider is off or its key was refused
});
const emit = defineEmits(["toggle", "open", "retry", "rekey", "remove"]);

const failed = computed(() => props.model.check && !props.model.check.ok);
// a service's own words can run long: the first sentence, the rest on hover
const reason = computed(() => {
	const message = props.model.check?.message ?? "";
	const first = message.split(/(?<=\.)\s/)[0];
	return first.length > 140 ? `${first.slice(0, 140)}…` : first;
});


const QUIET =
	"text-ink-gray-7 underline decoration-outline-gray-3 underline-offset-4 hover:decoration-outline-gray-6";
</script>
