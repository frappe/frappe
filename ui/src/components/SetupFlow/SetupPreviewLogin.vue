<template>
	<!-- Mirrors frappe/www/login.html; keep the two in step. -->
	<!-- Centred in the part of the preview window on screen; the frame sets both values. -->
	<div
		class="flex h-full justify-center bg-surface-base pt-16"
		style="
			width: var(--setup-preview-visible, 100%);
			margin-inline-start: var(--setup-preview-hidden, 0px);
		"
	>
		<div class="flex w-full max-w-[400px] flex-col gap-8 p-6">
			<div class="flex flex-col items-start gap-4">
				<div class="h-8 [&>*]:h-full [&>*]:w-auto">
					<slot name="logo" />
				</div>
				<div class="flex w-full flex-col gap-1.5">
					<h4 class="text-3xl-bold text-ink-gray-9">{{ text.title }}</h4>
					<p class="text-p-base text-ink-gray-6">{{ text.subtitle }}</p>
				</div>
			</div>
			<div class="flex flex-col gap-4">
				<div class="flex flex-col gap-1.5">
					<span class="text-base text-ink-gray-5">{{ text.email }}</span>
					<TextInput
						:model-value="email"
						variant="outline"
						size="md"
						readonly
						tabindex="-1"
					/>
				</div>
				<div class="flex flex-col items-end gap-2">
					<div class="flex w-full flex-col gap-1.5">
						<span class="text-base text-ink-gray-5">{{ text.password }}</span>
						<TextInput
							type="password"
							:model-value="'x'.repeat(passwordLength)"
							:placeholder="'•'.repeat(8)"
							variant="outline"
							size="md"
							readonly
							tabindex="-1"
						>
							<template #suffix>
								<span class="lucide-eye size-4 text-ink-gray-5" />
							</template>
						</TextInput>
					</div>
					<span class="text-base text-ink-gray-5">{{ text.forgot }}</span>
				</div>
			</div>
			<div class="flex flex-col gap-3">
				<Button
					data-slot="setup-preview-login-submit"
					variant="solid"
					size="md"
					:label="text.submit"
					:disabled="!ready"
					tabindex="-1"
				/>
				<Button v-if="emailLink" size="md" :label="text.emailLink" tabindex="-1" />
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Button, TextInput } from "frappe-ui";
import { computed } from "vue";

/** English defaults; pass translated text to relabel. */
export interface SetupPreviewLoginLabels {
	title: string;
	subtitle: string;
	email: string;
	password: string;
	forgot: string;
	submit: string;
	emailLink: string;
}

const props = withDefaults(
	defineProps<{
		/** The owner's email, filled in as the login page would after they sign out. */
		email: string;
		/** How many characters the owner has typed in the password step. Never the password. */
		passwordLength?: number;
		/** Whether the password step can save the password: Continue is enabled with it. */
		ready?: boolean;
		/** Shows "Login with Email Link", as /login does when email links are on. */
		emailLink?: boolean;
		labels?: Partial<SetupPreviewLoginLabels>;
	}>(),
	{ passwordLength: 0, ready: false, emailLink: true }
);

defineSlots<{
	/** The app's logo, sized to the login page's 32px. */
	logo?: () => unknown;
}>();

const defaults: SetupPreviewLoginLabels = {
	title: "Sign In",
	subtitle: "Welcome! Please sign in to continue.",
	email: "Email",
	password: "Password",
	forgot: "Forgot password?",
	submit: "Continue",
	emailLink: "Login with Email Link",
};
const text = computed(() => ({ ...defaults, ...props.labels }));
</script>
