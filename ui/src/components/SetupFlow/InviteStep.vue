<template>
	<div class="flex flex-col gap-2">
		<Alert
			v-if="failed.length"
			class="mb-2"
			theme="red"
			:title="text.failedTitle(failed.length)"
			:description="text.failedWho(failed.join(', '))"
		/>
		<div v-for="(row, index) in rows" :key="row.id" class="flex flex-col gap-1">
			<div class="relative flex items-center gap-1.5 sm:gap-2">
				<div class="min-w-0 flex-1">
					<FormControl
						v-model="row.email"
						type="email"
						:placeholder="text.placeholder"
						:aria-label="text.email(index + 1)"
						:disabled="sending || row.sent"
					>
						<template v-if="row.sent" #suffix>
							<Badge :label="text.sent" theme="green" variant="subtle" />
						</template>
					</FormControl>
				</div>
				<div class="w-40 shrink-0 sm:w-44">
					<FormControl
						v-model="row.role"
						type="select"
						:options="roles"
						:aria-label="text.role(index + 1)"
						:disabled="sending || row.sent"
					/>
				</div>
				<!-- Outside the column from sm up, so the fields line up with the text above. -->
				<Button
					v-if="!row.sent"
					variant="ghost"
					icon="lucide-x"
					class="shrink-0 text-ink-gray-6 sm:absolute sm:-end-8 sm:top-0"
					:aria-label="text.remove(index + 1)"
					:disabled="sending"
					@click="remove(index)"
				/>
			</div>
			<ErrorMessage v-if="problems[row.id]" :message="problems[row.id]" />
		</div>
		<Button
			variant="subtle"
			class="mt-1 self-start"
			icon-left="lucide-plus"
			:label="text.add"
			:disabled="sending"
			@click="rows.push(newRow())"
		/>
		<!-- The app can say more about an error it knows, like a link to fix it. -->
		<slot v-if="error" name="error" :message="error">
			<ErrorMessage :message="error" />
		</slot>

		<div class="mt-6 flex items-center gap-2">
			<Button
				v-if="!pending.length && sentRoles.size"
				variant="solid"
				:label="text.continue"
				@click="finish"
			/>
			<Button
				v-else
				variant="solid"
				:label="text.send"
				:loading="sending"
				:disabled="!canSend"
				@click="send"
			/>
			<Button
				variant="ghost"
				class="text-ink-gray-6"
				:label="text.skip"
				:disabled="sending"
				@click="emit('skip')"
			/>
			<Button
				v-if="canGoBack"
				variant="ghost"
				class="-me-2 ms-auto text-ink-gray-6"
				:label="text.back"
				:disabled="sending"
				@click="emit('back')"
			>
				<template #prefix>
					<span class="lucide-arrow-left size-4 rtl:rotate-180" />
				</template>
			</Button>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Alert, Badge, Button, ErrorMessage, FormControl } from "frappe-ui";
import { computed, onActivated, ref, watch } from "vue";

export interface InviteRole {
	label: string;
	value: string;
}

export interface Invitee {
	email: string;
	role: string;
}

/** What one `send` call did. Emails in `failed` were not invited; the rest were. */
export interface InviteOutcome {
	invited?: number;
	failed?: string[];
}

/** English defaults; pass translated text to relabel. Text with a number or names in it is a function. */
export interface InviteStepLabels {
	placeholder: string;
	email: (row: number) => string;
	role: (row: number) => string;
	remove: (row: number) => string;
	add: string;
	send: string;
	continue: string;
	skip: string;
	back: string;
	sent: string;
	invalid: string;
	duplicate: string;
	failed: string;
	/** Above the people who could not be invited. */
	failedTitle: (count: number) => string;
	failedWho: (emails: string) => string;
}

const props = withDefaults(
	defineProps<{
		roles: InviteRole[];
		/**
		 * Invites these people with this role, through the app's own invitation. Called once per
		 * role. Resolves with an outcome, a count of who was invited, or nothing when every email
		 * was invited.
		 */
		send: (role: string, emails: string[]) => Promise<InviteOutcome | number | void>;
		/** The role new rows start with. Defaults to the first role. */
		defaultRole?: string;
		/** The first row's role: who the app expects the owner to invite first. */
		firstRole?: string;
		labels?: Partial<InviteStepLabels>;
		/** Shows Back beside Skip, for flows that keep it with the step's own buttons. */
		canGoBack?: boolean;
	}>(),
	{ canGoBack: false }
);
const emit = defineEmits<{
	done: [result: { invited: number; roles: string[] }];
	skip: [];
	back: [];
	/** The valid emails typed so far, as they are typed, for a preview to show them. */
	invitees: [invitees: Invitee[]];
}>();

const defaults: InviteStepLabels = {
	placeholder: "name@example.com",
	email: (row) => `Email ${row}`,
	role: (row) => `Role ${row}`,
	remove: (row) => `Remove ${row}`,
	add: "Add another",
	send: "Send invites",
	continue: "Continue",
	skip: "Skip this step",
	back: "Back",
	sent: "Sent",
	invalid: "Enter a valid email address",
	duplicate: "This email is already in the list",
	failed: "Could not send the invites. Please try again.",
	failedTitle: (count) =>
		count === 1 ? "1 invite could not be sent" : `${count} invites could not be sent`,
	failedWho: (emails) => `Could not invite ${emails}.`,
};
const text = computed(() => ({ ...defaults, ...props.labels }));

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const roleFor = () => props.defaultRole ?? props.roles[0]?.value ?? "";
const normal = (email: string) => email.trim().toLowerCase();

type Row = { id: number; email: string; role: string; sent: boolean };
let lastId = 0;
const newRow = (role = roleFor()): Row => ({ id: ++lastId, email: "", role, sent: false });
const rows = ref<Row[]>([newRow(props.firstRole ?? roleFor()), newRow()]);

// The suggestion can change while the step is open, say after going back to another goal.
// It moves the first row only until a name is typed there.
watch(
	() => props.firstRole,
	(role) => {
		const first = rows.value[0];
		if (role && first && !first.email.trim()) first.role = role;
	}
);

const problems = computed(() => {
	const seen = new Set(rows.value.filter((row) => row.sent).map((row) => normal(row.email)));
	const found: Record<number, string> = {};
	for (const row of rows.value) {
		const email = normal(row.email);
		if (row.sent || !email) continue;
		if (!EMAIL.test(email)) found[row.id] = text.value.invalid;
		else if (seen.has(email)) found[row.id] = text.value.duplicate;
		seen.add(email);
	}
	return found;
});
const pending = computed(() => rows.value.filter((row) => !row.sent && row.email.trim()));
const canSend = computed(
	() => pending.value.length > 0 && !pending.value.some((row) => problems.value[row.id])
);

watch(
	rows,
	() =>
		emit(
			"invitees",
			rows.value
				.filter((row) => row.email.trim() && !problems.value[row.id])
				.map((row) => ({ email: row.email.trim(), role: row.role }))
		),
	{ deep: true }
);

function remove(index: number) {
	rows.value.splice(index, 1);
	if (!rows.value.length) rows.value.push(newRow());
}

const sending = ref(false);
const error = ref("");
// A kept-alive step shown again, say after the owner fixed what failed, starts without it.
onActivated(() => (error.value = ""));
const failed = ref<string[]>([]);
let invited = 0;
const sentRoles = ref(new Set<string>());

function outcomeOf(result: InviteOutcome | number | void, count: number): Required<InviteOutcome> {
	if (typeof result === "number") return { invited: result, failed: [] };
	const notInvited = result?.failed ?? [];
	return { invited: result?.invited ?? count - notInvited.length, failed: notInvited };
}

async function send() {
	if (!canSend.value) return;
	sending.value = true;
	error.value = "";
	failed.value = [];
	const byRole = new Map<string, Row[]>();
	for (const row of pending.value) byRole.set(row.role, [...(byRole.get(row.role) ?? []), row]);
	try {
		for (const [role, group] of byRole) {
			const outcome = outcomeOf(
				await props.send(
					role,
					group.map((row) => row.email.trim())
				),
				group.length
			);
			const notInvited = new Set(outcome.failed.map(normal));
			// Sent rows lock, so a retry after a later role fails does not send them twice.
			for (const row of group) row.sent = !notInvited.has(normal(row.email));
			invited += outcome.invited;
			if (group.some((row) => row.sent))
				sentRoles.value = new Set([...sentRoles.value, role]);
			failed.value.push(...group.filter((row) => !row.sent).map((row) => row.email.trim()));
		}
	} catch (e: unknown) {
		error.value = (e as { messages?: string[] })?.messages?.[0] || text.value.failed;
		return;
	} finally {
		sending.value = false;
	}
	// Someone could not be invited: the step stays, so the owner sees who and can fix it.
	if (!failed.value.length) finish();
}

function finish() {
	emit("done", { invited, roles: [...sentRoles.value] });
}
</script>
