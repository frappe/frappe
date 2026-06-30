<!--
	InviteUser — UI-only panel over the `useInviteUser` controller. Spread the
	controller with `v-bind="controller"`: its data members (roles, users, loading
	flags, error) bind as live values, and its verbs (invite, searchUsers) arrive as
	function props this panel drives directly. The panel owns the form UX (a user
	typeahead + email pills, role multi-select, submit, reset) and emits
	`invited` / `invalid` / `error` so hosts can hook side-effects without
	re-implementing the flow.

	No copy/label props and no heading: the panel renders standard frappe-ui fields
	with English defaults. To retitle, localize, or restyle a field, override its
	per-field slot (`#email` / `#roles` / `#submit`) and render the field with your
	own props — each slot's default is the standard field. Errors are field-scoped
	the frappe-ui way: the controller error binds to the email field's `:error` and
	renders inline under it (no global error line).

	There is intentionally no pending-invitations list here — the controller still
	fetches it lazily (`pendingInvites` / `load` / `reload`) for hosts that want it, but
	rendering one is out of scope for this block.
-->
<template>
	<form class="flex flex-col gap-4 text-ink-gray-9" @submit.prevent="submit">
		<!-- email: frappe-ui's experimental MultiEmailInput (chips + user typeahead,
		     self-labelling via useInputLabeling). The host debounces the search; the
		     controller error surfaces field-scoped through `:error`. -->
		<slot
			name="email"
			:value="emails"
			:set-value="(v: string[]) => (emails = v)"
			:options="users"
			:loading="usersLoading"
			:error="error"
			:search="onSearch"
			:on-invalid="onInvalidEmail"
		>
			<!-- attr order encodes a three-tier precedence: copy/presentation defaults
			     first, then `v-bind="emailProps"` (host overrides win over the defaults),
			     then the controlled wiring last (so the host can relabel/restyle but
			     can't hijack the model/options/error binding). -->
			<MultiEmailInput
				label="Invite by email"
				placeholder="Search users or type an email…"
				empty-text="No matching users"
				:create-label="(email) => `Invite &quot;${email}&quot;`"
				v-bind="emailProps"
				v-model="emails"
				:required="true"
				:options="users"
				:loading="usersLoading"
				:error="error as MultiEmailError"
				@update:query="onSearch"
				@invalid="onInvalidEmail"
			/>
		</slot>

		<!-- roles trigger sizes to its content (w-fit) instead of stretching to the
		     form width like the email field; the class falls through to MultiSelect's
		     LabelingWrapper. -->
		<slot
			name="roles"
			:value="selectedRoleValues"
			:set-value="(v: string[]) => (selectedRoleValues = v)"
			:options="roles"
		>
			<MultiSelect
				label="Roles"
				placeholder="Select roles"
				class="w-fit"
				v-bind="rolesProps"
				v-model="selectedRoleValues"
				:required="true"
				:options="roles"
			/>
		</slot>

		<slot name="submit" :submit="submit" :can-submit="canSubmit" :inviting="inviting">
			<Button
				type="submit"
				variant="solid"
				class="w-fit"
				:loading="inviting"
				:disabled="!canSubmit"
			>
				Send invites
			</Button>
		</slot>
	</form>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Button, MultiSelect, debounce, toast } from "frappe-ui";
import { MultiEmailInput } from "frappe-ui/experimental";
import type { InviteResult, InviteUserProps } from "./types";

// MultiEmailInput's `error` prop is `string | FrappeUIError`; the controller error is
// a Frappe error object (carries `.message` / `.messages`), which useInputLabeling
// reads. Narrow at the boundary instead of leaking `unknown` into the field.
type MultiEmailError = string | { message?: string; messages?: string[] } | null | undefined;

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
		usersLoading: false,
		inviting: false,
		error: null,
		showResultToasts: true,
	}
);

const emit = defineEmits<{
	invited: [result: InviteResult];
	invalid: [emails: string[]];
	error: [error: unknown];
}>();

// Kick off the controller's lazy initial fetch (pending / already-invited) only once
// the panel is actually shown.
onMounted(() => props.load?.());

const emails = ref<string[]>([]);
const selectedRoleValues = ref<string[]>([]);

const canSubmit = computed(
	() => emails.value.length > 0 && selectedRoleValues.value.length > 0 && !props.inviting
);

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
