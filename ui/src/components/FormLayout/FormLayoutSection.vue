<template>
  <div
    class="section"
    :class="[
      section.hideBorder ? 'pt-4' : 'border-t border-outline-gray-modals mt-5 pt-5',
    ]"
  >
    <CollapsibleSection
      class="flex sm:flex-row flex-col gap-4 text-lg font-medium"
      :class="{ 'px-3 sm:px-5': hasTabs }"
      :labelClass="['text-lg font-medium', { 'px-3 sm:px-5': hasTabs }]"
      :label="section.label"
      :hideLabel="section.hideLabel || !section.label"
      :opened="section.opened ?? true"
      :collapsible="section.collapsible ?? true"
      collapseIconPosition="right"
    >
      <template v-for="(column, index) in section.columns" :key="column.name ?? index">
        <FormLayoutColumn
          :class="{ 'mt-6': section.label && !section.hideLabel }"
          :column="column"
        />
      </template>
    </CollapsibleSection>
  </div>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import CollapsibleSection from './CollapsibleSection.vue'
import FormLayoutColumn from './FormLayoutColumn.vue'
import { HasTabsKey } from './types'
import type { Section } from './types'

defineProps<{ section: Section }>()

const hasTabs = inject(HasTabsKey)
</script>
