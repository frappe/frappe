<template>
	<LoginBox :title="title">
		<!-- Login -->
		<div
			v-if="!resetPasswordEmailSent"
			class="mx-auto w-full bg-white px-4 py-8 sm:mt-6 sm:w-96 sm:rounded-lg sm:px-8 sm:shadow-xl"
		>
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
				<div class="mt-2 text-left text-sm text-gray-700">
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

				<div class="mt-5 flex w-full flex-col gap-2">
					<ErrorMessage :message="session.login.error || resetPassword.error" />
					<Button variant="solid" :loading="session.login.loading">
						{{ !forgotPassword ? "Login" : "Reset Password" }}
					</Button>
				</div>
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
	</LoginBox>
</template>

<script setup>
import { ref, computed, inject, watch } from "vue"
import { useRoute } from "vue-router"

import { createResource } from "frappe-ui"
import LoginBox from "@/components/LoginBox.vue"

const email = ref(null)
const password = ref(null)
const resetPasswordEmailSent = ref(false)

const route = useRoute()
const session = inject("$session")

const forgotPassword = computed(() => route.query.forgot)
const title = computed(() => (forgotPassword.value ? "Reset Password" : "Login to Frappe"))

watch(
	() => forgotPassword.value,
	(_val) => {
		session.login.error = null
		resetPassword.error = null
		password.value = null
	}
)

const resetPassword = createResource({
	url: "frappe.core.doctype.user.user.reset_password",
	onSuccess: (_data) => {
		resetPasswordEmailSent.value = true
	},
})

const loginOrResetPassword = async () => {
	if (!forgotPassword.value) {
		session.login.submit({
			email: email.value,
			password: password.value,
		})
	} else {
		resetPassword.submit({ user: email.value })
	}
}
</script>
