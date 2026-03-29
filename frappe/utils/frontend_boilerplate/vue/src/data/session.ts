import { computed, reactive, ref } from 'vue'
import { useCall } from 'frappe-ui'
import router from '@/router'

export const sessionUser = ref<string | null>(getSessionUserFromCookie())

export const session = reactive({
  login: useCall({
    url: '/api/v2/method/login',
    immediate: false,
    onSuccess(data: any) {
      sessionUser.value = getSessionUserFromCookie()
      session.login.reset()
      router.replace(data.default_route || '/')
    },
  }),
  logout: useCall({
    url: '/api/v2/method/logout',
    method: 'POST',
    immediate: false,
    onSuccess() {
      sessionUser.value = getSessionUserFromCookie()
      window.location.href = '/login'
    },
  }),
  user: sessionUser,
  isLoggedIn: computed(() => sessionUser.value != null),
})

function getSessionUserFromCookie(): string | null {
  const cookies = new URLSearchParams(document.cookie.split('; ').join('&'))
  let user = cookies.get('user_id')
  if (user === 'Guest') {
    user = null
  }
  return user
}
