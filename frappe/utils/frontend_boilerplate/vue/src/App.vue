<template>
  <FrappeUIProvider>
    <router-view v-if="$route.name === 'Login'" />
    <AppLayout v-else-if="session.isLoggedIn">
      <router-view />
    </AppLayout>
    <router-view v-else />
  </FrappeUIProvider>
</template>

<script setup lang="ts">
import { FrappeUIProvider } from 'frappe-ui'
import AppLayout from '@/components/AppLayout.vue'
import { session } from '@/data/session'
</script>
