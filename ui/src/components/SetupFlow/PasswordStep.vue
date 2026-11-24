<template>
	<form class="flex flex-col gap-4" @submit.prevent="save">
		<div class="flex flex-col gap-1.5">
			<FormControl
				v-model="password"
				:type="shown ? 'text' : 'password'"
				variant="outline"
				size="md"
				autocomplete="new-password"
				:label="text.label"
				:placeholder="text.placeholder"
				:description="confirm ? undefined : text.hint"
				autofocus
			>
				<!-- On the label's own line, as on the reset password page, so it never moves the form. -->
				<template #label>
					<span class="flex items-center justify-between gap-2">
						{{ text.label }}
						<!-- Hidden here so the field's name stays "Password"; announced below. -->
						<span v-if="strength" aria-hidden="true">
							{{ text.strength }}
							<span class="font-medium" :class="STRENGTH_INK[strength.score]">{{
								text.levels[strength.score]
							}}</span>
						</span>
					</span>
				</template>
				<template #suffix>
					<button
						type="button"
						class="-me-1 flex size-6 items-center justify-center rounded text-ink-gray-5 hover:text-ink-gray-8"
						:aria-label="shown ? text.hide : text.show"
						:aria-pressed="shown"
						@click="shown = !shown"
					>
						<span :class="shown ? 'lucide-eye-off' : 'lucide-eye'" class="size-4" />
					</button>
				</template>
			</FormControl>
		</div>
		<div v-if="confirm" class="flex flex-col gap-1.5">
			<FormControl
				v-model="repeated"
				:type="shown ? 'text' : 'password'"
				variant="outline"
				size="md"
				autocomplete="new-password"
				:label="text.confirmLabel"
				:placeholder="text.confirmPlaceholder"
				:description="mismatch ? undefined : text.hint"
			/>
			<ErrorMessage v-if="mismatch" :message="text.mismatch" />
		</div>
		<Button
			type="submit"
			variant="solid"
			class="self-end"
			:label="text.save"
			:loading="saving"
			:disabled="!ready"
		/>
		<ErrorMessage :message="error" />
		<span class="sr-only" aria-live="polite">
			{{ strength ? `${text.strength} ${text.levels[strength.score]}` : "" }}
		</span>
	</form>
</template>

<script setup lang="ts">
import { Button, ErrorMessage, FormControl, call } from "frappe-ui";
import { computed, onBeforeUnmount, ref, watch } from "vue";

/** English defaults; pass translated text to relabel. */
export interface PasswordStepLabels {
	label: string;
	placeholder: string;
	hint: string;
	show: string;
	hide: string;
	save: string;
	failed: string;
	confirmLabel: string;
	confirmPlaceholder: string;
	mismatch: string;
	strength: string;
	/** One word per score, from 0 (weakest) to 4. */
	levels: [string, string, string, string, string];
}

const props = withDefaults(
	defineProps<{
		labels?: Partial<PasswordStepLabels>;
		/** Ask for the password twice. A typo here locks the user out once their session ends. */
		confirm?: boolean;
	}>(),
	{ confirm: true }
);
const emit = defineEmits<{
	done: [];
	/** Fires as the password is typed, with its length only: the value never leaves the step. */
	input: [length: number];
	/** Whether the password can be saved yet, for a preview to enable its own button with it. */
	ready: [ready: boolean];
}>();

const defaults: PasswordStepLabels = {
	label: "Password",
	placeholder: "At least 8 characters",
	hint: "At least 8 characters. Mixing in numbers and symbols makes it stronger.",
	show: "Show",
	hide: "Hide",
	save: "Save and continue",
	failed: "That password could not be saved. Try another.",
	confirmLabel: "Confirm password",
	confirmPlaceholder: "Type it again",
	mismatch: "The passwords do not match.",
	strength: "Strength:",
	levels: ["Poor", "Poor", "Average", "Good", "Great"],
};
// The colours of the reset password page's meter.
const STRENGTH_INK = [
	"text-ink-red-8",
	"text-ink-red-8",
	"text-ink-orange-8",
	"text-ink-blue-8",
	"text-ink-green-8",
];
const text = computed(() => ({ ...defaults, ...props.labels }));

const password = ref("");
watch(password, (value) => emit("input", value.length));

// The site's password policy scores it as it is typed. Without a policy the server returns
// nothing and no meter shows. As on the reset password page, the meter only informs: a
// password the policy refuses is refused on Save, with the server's reason, so nothing below
// the field appears or goes while typing.
type Strength = { score: number };
const strength = ref<Strength | null>(null);
let scoring: ReturnType<typeof setTimeout> | undefined;
// The last score stays up while the next one comes, so the meter changes in place.
watch(password, (value) => {
	error.value = "";
	clearTimeout(scoring);
	if (!value) strength.value = null;
	else scoring = setTimeout(() => score(value), 250);
});
onBeforeUnmount(() => clearTimeout(scoring));
async function score(value: string) {
	const result = await call("frappe.core.doctype.user.user.test_password_strength", {
		new_password: value,
	}).catch(() => null);
	if (value !== password.value || !result || !("score" in result)) return;
	strength.value = { score: Math.max(0, Math.min(4, Number(result.score) || 0)) };
}

const repeated = ref("");
// Only once the second entry is as long as the first, so it does not flash on every key.
const mismatch = computed(
	() =>
		props.confirm &&
		repeated.value.length > 0 &&
		repeated.value.length >= password.value.length &&
		repeated.value !== password.value
);
const ready = computed(
	() => password.value.length >= 8 && (!props.confirm || repeated.value === password.value)
);
watch(ready, (value) => emit("ready", value), { immediate: true });
const shown = ref(false);
const saving = ref(false);
const error = ref("");

async function save() {
	if (!ready.value) return;
	saving.value = true;
	error.value = "";
	try {
		await call("frappe.core.doctype.user.user.set_first_password", {
			new_password: password.value,
		});
		password.value = "";
		repeated.value = "";
		emit("done");
	} catch (e: unknown) {
		const { exc_type, messages } = (e as { exc_type?: string; messages?: string[] }) || {};
		// Refused because a password exists already, say after a reload mid-setup: the
		// step's job is done, so the flow moves on instead of trapping the user here.
		if (exc_type === "PermissionError") {
			password.value = "";
			repeated.value = "";
			emit("done");
			return;
		}
		error.value = messages?.[0] || text.value.failed;
	} finally {
		saving.value = false;
	}
}
</script>
