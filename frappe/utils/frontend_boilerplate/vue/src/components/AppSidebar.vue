<template>
  <nav class="flex h-full w-56 flex-shrink-0 flex-col border-r bg-surface-menu-bar">
    <div class="flex items-center px-4 py-3">
      <h1 class="text-lg font-semibold text-ink-gray-9">{{ app_title }}</h1>
    </div>
    <div class="flex-1 space-y-0.5 px-2">
      <router-link
        v-for="link in navigation"
        :key="link.name"
        :to="link.route"
        class="flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm transition"
        :class="[
          isActive(link.activeRegex)
            ? 'bg-surface-selected text-ink-gray-9 shadow-sm'
            : 'text-ink-gray-7 hover:bg-surface-gray-2',
        ]"
      >
        <component :is="link.icon" class="h-4 w-4 text-ink-gray-6" />
        {% raw %}{{ link.name }}{% endraw %}
      </router-link>
    </div>
    <div class="border-t px-3 py-3">
      <div class="flex items-center justify-between">
        <span class="truncate text-sm text-ink-gray-7">
          {% raw %}{{ session.user }}{% endraw %}
        </span>
        <Button variant="ghost" size="sm" @click="session.logout.submit()">
          <LucideLogOut class="h-4 w-4" />
        </Button>
      </div>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { session } from '@/data/session'

const route = useRoute()

const navigation = [
  {
    name: 'Home',
    route: { name: 'Home' },
    icon: 'LucideHome',
    activeRegex: /Home/,
  },
]

function isActive(regex: RegExp) {
  return route.name ? regex.test(route.name.toString()) : false
}
</script>
