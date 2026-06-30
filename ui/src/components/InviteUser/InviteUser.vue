<!--
	InviteUser — UI-only panel over the `useInviteUser` controller. Spread the
	controller with `v-bind="controller"`: its data members (roles, users, loading
	flags, error) bind as live values, and its verbs (invite, searchUsers) arrive as
	function props this panel drives directly. The panel owns the form UX (a user
	typeahead + email pills, role multi-select, result toasts, reset) and emits
	`invited` / `invalid` / `error` so hosts can hook side-effects without
	re-implementing the flow.

	There is intentionally no pending-invitations list here — the controller still
	fetches it lazily (`pendingInvites` / `load` / `reload`) for hosts that want it, but
	rendering one is out of scope for this block.
-->
<template>
	<div class="flex flex-col gap-5 text-ink-gray-9">
		<!-- header -->
		<slot name="header" :title="title">
			<h2 class="text-lg-semibold">{{ title }}</h2>
		</slot>

		<!-- form -->
		<slot
			name="form"
			:emails="emails"
			:roles="selectedRoleValues"
			:role-options="roles"
			:user-options="users"
			:inviting="inviting"
			:users-loading="usersLoading"
			:error="error"
			:search-users="(q: string) => searchUsers?.(q)"
			:submit="submit"
		>
			<form class="flex flex-col gap-4" @submit.prevent="submit">
				<!-- frappe-ui's experimental MultiEmailInput: chips + user typeahead,
				     self-labelling via useInputLabeling. The host debounces the search. -->
				<MultiEmailInput
					v-model="emails"
					:label="emailLabel"
					:required="true"
					:description="emailHint"
					:options="users"
					:loading="usersLoading"
					placeholder="Search users or type an email…"
					empty-text="No matching users"
					:create-label="(email) => `Invite &quot;${email}&quot;`"
					@update:query="onSearch"
					@invalid="onInvalidEmail"
				/>

				<MultiSelect
					v-model="selectedRoleValues"
					:label="rolesLabel"
					:required="true"
					:options="roles"
					:loading="rolesLoading"
					:placeholder="rolesPlaceholder"
				/>

				<Button
					type="submit"
					variant="solid"
					class="w-fit"
					:loading="inviting"
					:disabled="!canSubmit"
				>
					{{ submitLabel }}
				</Button>
			</form>
		</slot>

		<slot v-if="error" name="error" :error="error">
			<p class="text-p-sm text-ink-red-6">{{ errorMessage }}</p>
		</slot>
	</div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Button, MultiSelect, debounce, toast } from "frappe-ui";
import { MultiEmailInput } from "frappe-ui/experimental";
import type { InviteResult, InviteUserProps } from "./types";

// The controller's verbs come through `v-bind="controller"` as function props, so
// they must NOT also fall through onto the root element.
defineOptions({ inheritAttrs: false });

const props = withDefaults(
	defineProps<
		InviteUserProps & {
			invite?: (emails: string, roles: string[]) => Promise<InviteResult>;
			searchUsers?: (query: string) => void;
			/** Lazy initial fetch, called once on mount (provided by the controller). */
			load?: () => void;
		}
	>(),
	{
		roles: () => [],
		users: () => [],
		rolesLoading: false,
		usersLoading: false,
		inviting: false,
		error: null,
		title: "Invite users",
		showResultToasts: true,
		emailLabel: "Invite by email",
		emailHint:
			"Pick existing users, or type a new email and press Enter — separate several with a comma or newline.",
		rolesLabel: "Roles",
		rolesPlaceholder: "Select roles",
		submitLabel: "Send invites",
		errorText: "Something went wrong",
	}
);

const emit = defineEmits<{
	invited: [result: InviteResult];
	invalid: [emails: string[]];
	error: [error: unknown];
}>();

// Kick off the controller's lazy initial fetch (roles / pending / already-invited)
// only once the panel is actually shown.
onMounted(() => props.load?.());

const emails = ref<string[]>([]);
const selectedRoleValues = ref<string[]>([]);

const canSubmit = computed(
	() => emails.value.length > 0 && selectedRoleValues.value.length > 0 && !props.inviting
);

// Surface the real backend message (e.g. a permission error) in the default
// error slot instead of a blanket "something went wrong".
const errorMessage = computed(() => {
	const e = props.error as { messages?: string[]; message?: string } | null | undefined;
	return e?.messages?.[0] || e?.message || props.errorText;
});

// MultiEmailInput emits `update:query` on every keystroke; debounce before
// hitting the controller's user search (the old in-component debounce moved here).
const onSearch = debounce((query: string) => props.searchUsers?.(query), 250);

function onInvalidEmail(email: string) {
	toast.error(`Invalid email: ${email}`);
	emit("invalid", [email]);
}

/** Standard per-bucket toasts (suppress with `:show-result-toasts="false"` + `@invited`). */
function showResultToasts(result: InviteResult) {
	const join = (list: string[]) => list.join(", ");
	if (result.invited_emails.length) toast.success(`${join(result.invited_emails)} invited`);
	if (result.disabled_user_emails.length)
		toast.info(`${join(result.disabled_user_emails)} already present and disabled`);
	if (result.pending_invite_emails.length)
		toast.info(`${join(result.pending_invite_emails)} already invited`);
	if (result.accepted_invite_emails.length)
		toast.info(`${join(result.accepted_invite_emails)} already present`);
}

async function submit() {
	if (!canSubmit.value) return;
	try {
		const result = await props.invite?.(emails.value.join(", "), selectedRoleValues.value);
		if (!result) return;
		if (props.showResultToasts) showResultToasts(result);
		emit("invited", result);
		emails.value = [];
		selectedRoleValues.value = [];
	} catch (e) {
		emit("error", e);
	}
}
</script>
