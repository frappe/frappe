<!-- The dialog behind the bar's assign, tag, follow, share and seen actions: it names the records, collects the
     user or tags, and reports what failed. A run past the async threshold is followed in the background. -->
<template>
	<Dialog v-model="open" :title="title" size="sm" :actions="actions" :dismissible="!running">
		<template #default>
			<div class="flex flex-col gap-3">
				<p class="text-base text-ink-gray-6">{{ description }}</p>

				<div v-if="pickUsers" class="flex flex-col gap-2">
					<AssigneePicker
						:assignees="people"
						@assign="(_user, person) => person && people.push(person)"
						@unassign="(user) => (people = people.filter(({ id }) => id !== user))"
					/>
					<Checkbox
						v-if="request.kind === 'share'"
						v-model="canWrite"
						:label="__('Can edit')"
					/>
				</div>

				<div v-if="pickTags" class="flex flex-wrap items-center gap-1.5">
					<TagChip v-for="tag in chosen" :key="tag" :tag="tag" />
					<TagPicker :session="session" side="bottom" :creatable="kind === 'add_tags'">
						<template #trigger>
							<Button
								variant="subtle"
								icon-left="lucide-plus"
								:label="chosen.length ? __('Edit tags') : __('Pick tags')"
							/>
						</template>
					</TagPicker>
				</div>

				<p
					v-if="failure"
					role="alert"
					class="max-h-48 overflow-y-auto whitespace-pre-line text-sm text-ink-red-4"
				>
					{{ failure }}
				</p>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { bulkCollaborate, isBulkQueued } from "@framework/ui/api";
import { Button, Checkbox, Dialog, toast } from "frappe-ui";
import { computed, ref, watch } from "vue";
import { __, __n } from "@/i18n";
import { followBulkRun } from "@/shell/bulkRuns";
import AssigneePicker from "@/pages/record/panel/AssigneePicker.vue";
import type { Person } from "@/pages/record/panel/people";
import TagChip from "@/pages/record/panel/TagChip.vue";
import TagPicker from "@/pages/record/panel/TagPicker.vue";
import { useTagSession } from "@/pages/record/panel/tagSession";
import { recolourTag } from "@/tagApi";
import { callsFor, kindLabel, scopeText, type CollabRequest } from "./bulkCollaboration";

const props = defineProps<{ request: CollabRequest; doctype: string; reload: () => void }>();
const emit = defineEmits<{ close: [] }>();

const open = ref(true);
watch(open, (isOpen) => !isOpen && emit("close"));
const running = ref(false);
const failure = ref("");

const kind = props.request.kind;
const verb = kind === "assign" ? __("Assign") : kindLabel(kind);
const pickUsers = kind === "assign" || kind === "share";
const pickTags = kind === "add_tags" || kind === "remove_tags";

const people = ref<Person[]>([]);
const canWrite = ref(false);
const chosen = ref<string[]>([]);
const colors = ref<Record<string, string>>({});

const session = useTagSession(
	() => chosen.value,
	async ({ added, removed }) => {
		for (const { tag, color } of added) if (color) colors.value[tag] = color;
		chosen.value = [
			...chosen.value.filter((tag) => !removed.includes(tag)),
			...added.map(({ tag }) => tag),
		];
	},
	// A tag picked here has no Tag row until the run creates it, so its colour stays local.
	async (tag, color) => {
		if (tag in colors.value) colors.value[tag] = color;
		else await recolourTag(tag, color);
	}
);

const scope = computed(() => scopeText(props.request));
const title = computed(() => __("{0}: {1}", [verb, scope.value]));
const description = computed(() => {
	if (kind === "clear_assignment")
		return __("This cancels every assignment on {0}.", [scope.value]);
	if (kind === "apply_assignment_rule")
		return __("The doctype's assignment rules run again on {0}.", [scope.value]);
	if (pickUsers) return __("Pick the people for {0}.", [scope.value]);
	if (pickTags) return __("Pick the tags for {0}.", [scope.value]);
	return __("{0} on {1}.", [verb, scope.value]);
});

const ready = computed(() =>
	pickUsers ? people.value.length > 0 : !pickTags || chosen.value.length > 0
);
const actions = computed(() =>
	failure.value
		? [{ label: __("Close"), onClick: () => (open.value = false) }]
		: [
				{
					label: verb,
					variant: "solid",
					loading: running.value,
					disabled: !ready.value,
					onClick: confirm,
				},
		  ]
);

async function confirm() {
	running.value = true;
	const failed: string[] = [];
	let done = 0;
	let queued = false;
	try {
		const input = {
			users: people.value.map(({ id }) => id),
			tags: chosen.value,
			colors: colors.value,
			canWrite: canWrite.value,
		};
		for (const { part, method, bodies } of callsFor(kind, input)) {
			for (const body of bodies) {
				const { data } = await bulkCollaborate(
					props.doctype,
					part,
					method,
					props.request.selection,
					body
				);
				if (isBulkQueued(data)) {
					queued = true;
					followBulkRun(data.task_id, props.reload);
					continue;
				}
				done = Math.max(done, data.done.length);
				failed.push(...data.failed.map(({ name, error }) => `${name}: ${error}`));
			}
		}
	} catch (error) {
		failed.push(error instanceof Error ? error.message : String(error));
	} finally {
		running.value = false;
	}
	props.reload();
	if (queued) toast.info(__("Running in the background"));
	if (done) toast.success(__n("Done on {0} record", "Done on {0} records", done, [done]));
	if (!failed.length) return void (open.value = false);
	failure.value = [...new Set(failed)].join("\n");
}
</script>
