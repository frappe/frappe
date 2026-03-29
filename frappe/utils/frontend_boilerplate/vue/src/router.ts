import { createRouter, createWebHistory } from 'vue-router'
import { session } from './data/session'

const router = createRouter({
  history: createWebHistory(__FRONTEND_ROUTE__ + '/'),
  routes: [
    {
      path: '/',
      redirect: '/home',
    },
    {
      path: '/home',
      name: 'Home',
      component: () => import('@/pages/Home.vue'),
    },
    {
      path: '/todos/:id',
      name: 'TodoDetail',
      component: () => import('@/pages/TodoDetail.vue'),
      props: true,
    },
  ],
})

router.beforeEach((to, from) => {
  if (to.name !== 'Login' && !session.isLoggedIn) {
    window.location.href = '/login'
    return false
  }
})

export default router
