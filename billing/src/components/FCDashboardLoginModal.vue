<template>
	<Dialog
		v-model="show"
		:options="{
			title: loginLink ? 'Login successful!' : 'Login to Frappe Cloud Dashboard',
		}"
	>
		<template #body-content>
			<div class="text-base leading-5">
				<div v-if="verificationCodeSent" class="flex flex-col gap-4">
					<p>
						Verification code has been sent to your email id
						<b>{{ email }}</b>
					</p>
					<FormControl
						v-model="verification_code"
						type="text"
						label="Verification Code"
						placeholder="Enter the verification code"
					/>
					<ErrorMessage v-if="verifyAndLogin.error" :message="verifyAndLogin.error" />
				</div>
				<div v-else-if="loginLink">
					<p>You will be redirected to the Frappe Cloud Dashboard</p>
					<p>
						If you haven't been redirected,
						<a class="underline" :href="loginLink" target="_blank">
							Click here to login
						</a>
					</p>
				</div>
				<div v-else>
					<p>
						Send a verification code to your email id
						<b>{{ email }}</b>
					</p>
				</div>
			</div>
		</template>
		<template v-if="!loginLink" #actions>
			<Button
				v-if="verificationCodeSent"
				class="w-full mb-2"
				label="Din't receive the code? Resend"
				:loading="sendVerificationCode.loading"
				@click="() => sendVerificationCode.fetch()"
			/>
			<Button
				v-if="verificationCodeSent"
				class="w-full"
				label="Verify & Login"
				variant="solid"
				:disabled="!verification_code"
				:loading="verifyAndLogin.loading"
				@click="() => verifyAndLogin.fetch()"
			/>
			<Button
				v-else
				class="w-full"
				label="Send verification code"
				variant="solid"
				:loading="sendVerificationCode.loading"
				@click="() => sendVerificationCode.fetch()"
			/>
		</template>
	</Dialog>
</template>

<script setup>
import { Button, Dialog, FormControl, ErrorMessage, createResource } from 'frappe-ui'
import { ref, computed, inject } from 'vue'

const show = defineModel()

const team = inject('team')

const email = computed(() => maskEmail(team.data?.user))

function maskEmail(emailId) {
	if (!emailId) return ''
	const [username, domain] = emailId.split('@')
	let domainParts = domain.split('.')
	return `${username.slice(0, 2)}****@${domainParts[0].slice(0, 2)}****.${domainParts[1]}`
}

const verification_code = ref('')
const verificationCodeSent = ref(false)

const sendVerificationCode = createResource({
	url: 'frappe.integrations.frappe_providers.frappecloud_billing.send_verification_code',
	onSuccess: () => {
		verificationCodeSent.value = true
	},
})

const loginLink = ref(null)

const verifyAndLogin = createResource({
	url: 'frappe.integrations.frappe_providers.frappecloud_billing.verify_and_login',
	makeParams: () => {
		return { verification_code: verification_code.value }
	},
	onSuccess: ({ base_url, login_token }) => {
		loginLink.value = `${base_url}/api/method/press.api.developer.saas.login_to_fc?token=${login_token}`
		window.open(loginLink.value, '_blank')
		verificationCodeSent.value = false
	},
})
</script>
