<!-- The `people` built-in: who the record is assigned to and shared with, read from `docinfo`.
     Each row edits with the right `docinfo.permissions` carries, and reads otherwise. -->
<template>
	<PeopleRow label="Assigned to" icon="lucide-user">
		<AssigneePicker
			v-if="canWrite"
			:assignees="assignees"
			:call="page.call"
			@assign="actions.assign"
			@unassign="actions.unassign"
		/>
		<span v-else class="flex min-w-0 px-1.5 py-1">
			<PeopleAvatars :people="assignees" placeholder="Not assigned" />
		</span>
	</PeopleRow>

	<PeopleRow label="Shared with" icon="lucide-share-2">
		<!-- w-fit: a grid child stretches, and the hover would run the column's whole width. -->
		<button
			v-if="canShare"
			type="button"
			class="flex w-fit min-w-0 items-center rounded-1 px-1.5 py-1 transition hover:bg-surface-gray-2"
			:aria-label="shared.length ? 'Change who this record is shared with' : 'Share with…'"
			data-share
			@click="openShare"
		>
			<PeopleAvatars :people="shared" placeholder="Add people…" />
		</button>
		<span v-else class="flex min-w-0 px-1.5 py-1">
			<PeopleAvatars :people="shared" placeholder="Not shared" />
		</span>
	</PeopleRow>
</template>

<script setup lang="ts">
import { computed, inject, markRaw } from "vue";
import AssigneePicker from "./AssigneePicker.vue";
import { PanelContextKey } from "./context";
import { assigneesOf, sharedWith } from "./people";
import { peopleActions } from "./peopleActions";
import PeopleAvatars from "./PeopleAvatars.vue";
import PeopleRow from "./PeopleRow.vue";
import ShareDialog from "./ShareDialog.vue";

const context = inject(PanelContextKey)!;
const page = context.controller.page;
const actions = peopleActions(context);

const assignees = computed(() => assigneesOf(context.docinfo.value));
const shared = computed(() => sharedWith(context.docinfo.value));

const canWrite = computed(() => Boolean(context.docinfo.value?.permissions?.write));
const canShare = computed(() => Boolean(context.docinfo.value?.permissions?.share));

// The dialog reads the context, not a copy: a share it makes shows in its own list.
function openShare() {
	page.dialog.open(
		markRaw(ShareDialog),
		{ context: markRaw(context) },
		{ title: "Share this record" }
	);
}
</script>
