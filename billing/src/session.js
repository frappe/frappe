import { createResource } from 'frappe-ui'
import router from '@/router'
import { ref, computed } from 'vue'

let user = ref(null)
const isLoggedIn = computed(() => !!user.value)

export function getSession() {
	function sessionUser() {
		let cookies = new URLSearchParams(document.cookie.split('; ').join('&'))
		let _sessionUser = cookies.get('user_id')
		let _fullName = cookies.get('full_name')
		let _imageURL = cookies.get('user_image')
		if (_sessionUser === 'Guest') {
			_sessionUser = null
		}
		return {
			name: _sessionUser,
			fullName: _fullName,
			imageURL: _imageURL,
		}
	}

	const isFCSite = createResource({
		url: 'frappe.integrations.frappe_providers.frappecloud_billing.is_fc_site',
		cache: 'isFCSite',
		auto: true,
		transform: (data) => Boolean(data),
	})

	user.value = sessionUser()

	const login = createResource({
		url: 'login',
		onError() {
			throw new Error('Invalid email or password')
		},
		onSuccess() {
			user.value = sessionUser()
			login.reset()
			router.replace({ path: '/' })
		},
	})

	const logout = createResource({
		url: 'logout',
		onSuccess() {
			isFCSite.reload()
			user.value = null
			window.location.href = '/'
		},
	})

	return {
		user,
		isLoggedIn,
		login,
		logout,
		isFCSite,
	}
}
