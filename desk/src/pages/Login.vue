<template>
	<div class="relative h-full">
		<div class="relative z-10 mx-auto py-8 sm:w-max sm:py-32">
			<div class="flex">
				<div class="mx-auto flex items-center space-x-2">
					<AppLogo class="inline-block h-7 w-7" />
					<span class="select-none text-xl font-semibold tracking-tight text-gray-900">
						Frappe
					</span>
				</div>
			</div>

			<!-- Login Box -->
			<div
				v-if="!resetPasswordEmailSent"
				class="mx-auto w-full bg-white px-4 py-8 sm:mt-6 sm:w-96 sm:rounded-lg sm:px-8 sm:shadow-xl"
			>
				<div class="mb-6 text-center" v-if="title">
					<span class="text-center text-lg font-medium leading-5 tracking-tight text-gray-900">
						{{ title }}
					</span>
				</div>

				<form class="flex flex-col" @submit.prevent="loginOrResetPassword">
					<FormControl
						label="Email"
						placeholder="johndoe@mail.com"
						v-model="email"
						name="email"
						autocomplete="email"
						:type="email !== 'Administrator' ? 'email' : 'text'"
						required
					/>
					<FormControl
						class="mt-4"
						v-if="!forgotPassword"
						label="Password"
						type="password"
						placeholder="•••••"
						v-model="password"
						name="password"
						autocomplete="current-password"
						required
					/>
					<div class="mt-2 text-sm">
						<router-link v-if="forgotPassword" to="/login"> I remember my password </router-link>
						<router-link
							v-else
							:to="{
								name: 'Login',
								query: { forgot: 1 },
							}"
						>
							Forgot Password?
						</router-link>
					</div>

					<ErrorMessage :message="session.login.error" class="mt-4" />
					<Button class="mt-4" variant="solid" :loading="session.login.loading">
						{{ !forgotPassword ? "Log in with email" : "Reset Password" }}
					</Button>
				</form>
			</div>

			<!-- Reset Password Message -->
			<div
				v-else
				class="mx-auto w-full bg-white px-4 py-8 sm:mt-6 sm:w-96 sm:rounded-lg sm:px-8 sm:shadow-xl"
			>
				<div class="mb-6 text-center" v-if="title">
					<span class="text-center text-lg font-medium leading-5 tracking-tight text-gray-900">
						{{ title }}
					</span>
				</div>

				<div class="text-p-base text-gray-700">
					<p>
						We have sent an email to <span class="font-semibold">{{ email }}</span
						>. Please click on the link received to reset your password.
					</p>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, computed, inject } from "vue"
import { useRoute } from "vue-router"

import AppLogo from "@/components/icons/AppLogo.vue"
import { createResource } from "frappe-ui"

const email = ref(null)
const password = ref(null)
const errorMessage = ref(null)
const resetPasswordEmailSent = ref(false)

const route = useRoute()
const session = inject("$session")

const forgotPassword = computed(() => route.query.forgot)
const title = computed(() => (forgotPassword.value ? "Reset Password" : "Log in to your account"))

const loginOrResetPassword = async () => {
	if (!forgotPassword.value) {
		session.login.submit({
			email: email.value,
			password: password.value,
		})
	} else {
		resetPassword.reload()
	}
}

const resetPassword = createResource({
	url: "frappe.core.doctype.user.user.reset_password",
	data: { user: email.value },
	onSuccess: (_data) => {
		resetPasswordEmailSent.value = true
	},
})
</script>
