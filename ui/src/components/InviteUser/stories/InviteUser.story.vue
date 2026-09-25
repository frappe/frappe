<template>
	<div class="max-w-xl p-6">
		<!-- ── InviteUser playground ───────────────────────────────────────────
		     The panel is UI only — it renders an injected controller. Here we hand
		     it a *mock* controller (fixture roles/users + in-memory verbs) instead
		     of useInviteUser(), so it runs with no backend and doubles as the
		     no-UI-regression check. -->
		<h3 class="mb-3 text-xl-semibold text-ink-gray-9">InviteUser</h3>

		<div class="mb-4 flex flex-wrap items-center gap-4">
			<Switch v-model="errored" label="Error" />
			<Switch v-model="showResultToasts" label="Result toasts" />
		</div>

		<div class="rounded-lg border border-outline-gray-2 p-4">
			<InviteUser
				v-bind="controller"
				:show-result-toasts="showResultToasts"
				@invited="(r) => log('invited', r)"
				@invalid="(e) => log('invalid', e)"
				@error="(e) => log('error', e)"
			/>
		</div>

		<!-- ── Relabelled via emailProps / rolesProps ──────────────────────────
		     The lightweight customization path: forward props onto the fields to
		     relabel/restyle without a slot. The wiring (model/options/error) stays
		     owned by the panel. Use a field slot only when you need to replace the
		     rendered field wholesale. -->
		<h4 class="mb-2 mt-8 text-lg-semibold text-ink-gray-9">emailProps / rolesProps</h4>
		<div class="rounded-lg border border-outline-gray-2 p-4">
			<InviteUser
				v-bind="controller"
				:show-result-toasts="showResultToasts"
				:email-props="{
					label: 'Teammate emails',
					description: 'Custom label supplied via emailProps.',
					placeholder: 'name@company.com',
				}"
				:roles-props="{ label: 'Access level' }"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { Switch } from "frappe-ui";
import InviteUser from "../InviteUser.vue";
import type { InviteResult, InviteStore, RoleOption, UserOption } from "../types";

const errored = ref(false);
const showResultToasts = ref(true);

const roleFixtures: RoleOption[] = [
	{ label: "System Manager", value: "System Manager" },
	{ label: "Sales User", value: "Sales User" },
	{ label: "Sales Manager", value: "Sales Manager" },
];

const userFixtures: UserOption[] = [
	{
		label: "Ada Lovelace",
		value: "ada@example.com",
		avatar: "https://i.pravatar.cc/80?u=ada@example.com",
	},
	{
		label: "Grace Hopper",
		value: "grace@example.com",
		avatar: "https://i.pravatar.cc/80?u=grace@example.com",
	},
	{ label: "Alan Turing", value: "alan@example.com" },
];

const users = ref<UserOption[]>([]);
const usersLoading = ref(false);

function log(...args: unknown[]) {
	console.log("[InviteUser]", ...args);
}

const wait = (ms = 300) => new Promise((r) => setTimeout(r, ms));

// a mock of the useInviteUser() controller — fixtures + in-memory verbs
const controller = reactive({
	roles: roleFixtures,
	users,
	usersLoading,
	inviting: false,
	error: computed(() => (errored.value ? { messages: ["Permission denied"] } : null)),
	// the real controller fetches lazily on mount; the mock has nothing to fetch
	load: () => {},
	invite: async (emails: string, roles: string[]): Promise<InviteResult> => {
		await wait();
		const list = emails
			.split(",")
			.map((e) => e.trim())
			.filter(Boolean);
		log("invite", { roles });
		return {
			invited_emails: list,
			disabled_user_emails: [],
			pending_invite_emails: [],
			accepted_invite_emails: [],
		};
	},
	searchUsers: async (query: string) => {
		usersLoading.value = true;
		await wait(200);
		const q = query.trim().toLowerCase();
		users.value = q
			? userFixtures.filter(
					(u) => u.label.toLowerCase().includes(q) || u.value.toLowerCase().includes(q)
			  )
			: userFixtures;
		usersLoading.value = false;
	},
}) as unknown as InviteStore;
</script>
