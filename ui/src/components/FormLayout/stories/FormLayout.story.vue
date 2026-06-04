<template>
  <div class="flex flex-col h-screen">
    <Tabs v-model="activeTab" :tabs="tabs">
      <template #tab-panel="{ tab }">
        <StaticSchema v-if="tab.key === 'static'" />
        <DoctypeLayout v-else-if="tab.key === 'doctype'" :doctype="doctype" />
      </template>
    </Tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Tabs } from 'frappe-ui'
import StaticSchema from './StaticSchema.story.vue'
import DoctypeLayout from './DoctypeLayout.story.vue'
import { useDoctypeLayout } from '../useDoctypeLayout'

const doctype = 'CRM Lead'

// Warm the memo cache up-front so the meta resolves while the default tab is
// active. When DoctypeLayout later mounts it reads the cached layout — no async
// update fires inside a TabsContent mid-transition (which crashed reka-ui).
useDoctypeLayout(doctype)

const tabs = [
  { key: 'static', label: 'Hand-written schema' },
  { key: 'doctype', label: `useDoctypeLayout('${doctype}')` },
]
const activeTab = ref(0)
</script>
