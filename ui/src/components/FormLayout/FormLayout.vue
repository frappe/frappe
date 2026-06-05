<template>
  <div
    class="flex flex-col"
    :class="{ 'border border-outline-gray-1 border-outline-gray-modals rounded-lg': hasTabs }"
  >
    <Tabs
      v-model="tabIndex"
      as="div"
      :tabs="visibleTabs"
      :class="[
        !hasTabs ? `[&_[role='tablist']]:hidden` : '',
        `[&_[role='tablist']::-webkit-scrollbar]:h-0 [&_[role='tab']]:shrink-0 [&_[role='tabpanel']]:overflow-visible !overflow-visible`,
      ]"
    >
      <template #tab-panel="{ tab }">
        <div class="sections" :class="{ 'my-4 sm:my-5': hasTabs }">
          <template v-for="(section, index) in tab.sections" :key="section.name ?? index">
            <FormLayoutSection :section="section" />
          </template>
        </div>
      </template>
    </Tabs>
  </div>
</template>

<script setup lang="ts">
import { Tabs } from 'frappe-ui'
import { computed, provide, ref } from 'vue'
import FormLayoutSection from './FormLayoutSection.vue'
import { useFieldTypes } from './useFieldTypes'
import { resolveLayout } from './resolveLayout'
import { CommitKey, DocKey, HasTabsKey, ResolveFieldKey, UpdateKey } from './types'
import type { FormLayoutSchema } from './types'

const props = defineProps<{ layout: FormLayoutSchema }>()

const doc = defineModel<Record<string, any>>('doc', { required: true })
const emit = defineEmits<{ change: [fieldname: string, value: any] }>()

const tabIndex = ref(0)

// Bake conditional visibility/mandatory/read-only against the live doc. Reading
// `doc.value` makes this re-resolve as the user edits, so dependent fields show,
// hide, or flip required/read-only reactively.
const resolvedLayout = computed(() => resolveLayout(props.layout, doc.value))

const visibleTabs = computed(() =>
  resolvedLayout.value
    .filter((tab) => !tab.hidden)
    .map((tab) => ({
      ...tab,
      label: tab.label ?? '',
      sections: tab.sections.filter((section) => !section.hidden),
    })),
)

const hasTabs = computed(
  () =>
    visibleTabs.value.length > 1 ||
    (visibleTabs.value.length === 1 && Boolean(visibleTabs.value[0].label)),
)

// Live value sync — runs on every keystroke/selection. Keeps `doc` (and the
// conditional visibility computed above) reactive while the user edits.
function update(fieldname: string, value: any) {
  doc.value[fieldname] = value
}

// Commit — runs when a field is finished editing (blur / selection). The seam
// the field-change scripting layer will hook; for now it just surfaces `@change`.
function commit(fieldname: string, value: any) {
  emit('change', fieldname, value)
}

const { resolve } = useFieldTypes()

provide(DocKey, doc)
provide(UpdateKey, update)
provide(CommitKey, commit)
provide(ResolveFieldKey, resolve)
provide(HasTabsKey, hasTabs)
</script>

<style scoped>
/* Hide sections that render no fields. */
.section:not(:has(.field)) {
  display: none;
}

/* The first section with fields sits flush under the tab strip. */
.section:has(.field):nth-child(1 of .section:has(.field)) {
  border-top: none;
  margin-top: 0;
  padding-top: 0;
}
</style>
