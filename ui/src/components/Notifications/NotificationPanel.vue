<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Button, TabButtons } from 'frappe-ui'
import LucideCheckCheck from '~icons/lucide/check-check'
import LucideX from '~icons/lucide/x'
import NotificationItem from './NotificationItem.vue'
import { useNotifications } from './useNotifications'
import type { NotificationLog, NotificationPanelProps } from './types'

const props = withDefaults(defineProps<NotificationPanelProps>(), {
  showMarkAllRead: true,
  showClose: true,
  pageLength: 20,
  title: 'Notifications',
})

const emit = defineEmits<{
  close: []
  'mark-all-read': []
  'item-click': [n: NotificationLog]
  'update:unread-count': [count: number]
}>()

const activeTab = ref<string | undefined>(props.tabs?.[0]?.label)

const {
  notifications,
  unreadCount,
  hasNextPage,
  markAsRead,
  markAllAsRead,
  markSeen,
  setServerFilters,
  loadMore,
} = useNotifications({
  fields: props.fields,
  pageLength: props.pageLength,
  appName: props.appName,
  socket: props.socket,
})

const currentTab = computed(() =>
  props.tabs?.find((t) => t.label === activeTab.value),
)

// rows to render: client-side predicate if the active tab defines one
const visibleNotifications = computed<NotificationLog[]>(() => {
  const fn = currentTab.value?.filterFn
  return fn ? notifications.value.filter(fn) : notifications.value
})

function tabCount(tab: NonNullable<NotificationPanelProps['tabs']>[number]) {
  if (tab.count === 'unread') return unreadCount.value
  if (typeof tab.count === 'function') return tab.count(notifications.value)
  return undefined
}

// buttons for the frappe-ui TabButtons segmented control. TabButtons has no
// per-button badge slot, so a non-zero count is surfaced inline in the label.
const tabButtons = computed(() =>
  (props.tabs ?? []).map((tab) => {
    const count = tabCount(tab)
    return {
      label: count ? `${tab.label} (${count})` : tab.label,
      value: tab.label,
    }
  }),
)

// switch server-side filters when the tab changes (the app scope, if any, is preserved)
watch(activeTab, () => {
  setServerFilters(currentTab.value?.filters ?? {})
})

watch(unreadCount, (c) => emit('update:unread-count', c), { immediate: true })

onMounted(() => markSeen())

function onItemClick(n: NotificationLog) {
  markAsRead(n.name)
  emit('item-click', n)
  props.onItemClick?.(n)
}

function onMarkAll() {
  markAllAsRead()
  emit('mark-all-read')
}
</script>

<template>
  <div class="flex flex-col bg-surface-white text-ink-gray-9 w-full h-full">
    <!-- header -->
    <slot name="header" :unread-count="unreadCount">
      <div class="flex items-center gap-2 px-4 py-2 border-b">
        <span class="font-medium mr-auto">{{ title }}</span>
        <Button
          v-if="showMarkAllRead"
          variant="ghost"
          tooltip="Mark all as read"
          :icon="LucideCheckCheck"
          size="sm"
          @click="onMarkAll"
        />
        <Button
          v-if="showClose"
          variant="ghost"
          size="sm"
          tooltip="Close"
          :icon="LucideX"
          @click="emit('close')"
        />
      </div>
    </slot>

    <!-- tabs -->
    <TabButtons
      v-if="tabs?.length"
      v-model="activeTab"
      :buttons="tabButtons"
      class="px-4 py-2 [&_button]:w-full [&_div]:w-full"
    />

    <!-- body -->
    <div class="flex-1 overflow-y-auto">
      <template v-if="visibleNotifications.length">
        <template v-for="n in visibleNotifications" :key="n.name">
          <!-- fully custom row -->
          <div v-if="$slots.item" @click="onItemClick(n)">
            <slot name="item" :notification="n" />
          </div>
          <!-- default row -->
          <NotificationItem
            v-else
            :notification="n"
            :icon="icon?.(n)"
            @click="onItemClick"
          />
        </template>

        <div v-if="hasNextPage" class="p-3 text-center">
          <Button label="Load more" size="sm" @click="loadMore" />
        </div>
      </template>

      <slot v-else name="empty">
        <div class="py-12 text-center text-sm text-ink-gray-5">
          No notifications to show
        </div>
      </slot>
    </div>
  </div>
</template>
