<script setup lang="ts">
import { computed } from 'vue'
import { Avatar, dayjs } from 'frappe-ui'
import type { NotificationItemStyle, NotificationLog, NotificationType } from './types'

const props = defineProps<{
  notification: NotificationLog
  typeMeta?: NotificationType
  itemStyle?: (n: NotificationLog) => NotificationItemStyle
}>()

const emit = defineEmits<{
  click: [n: NotificationLog]
}>()

// color token -> tint classes applied to the Avatar; falls back to gray
const COLOR_CLASS: Record<string, string> = {
  blue: '!bg-surface-blue-1 text-ink-blue-2',
  green: '!bg-surface-green-1 text-ink-green-2',
  red: '!bg-surface-red-1 text-ink-red-4',
  orange: '!bg-surface-amber-1 text-ink-amber-3',
  yellow: '!bg-surface-amber-1 text-ink-amber-3',
  gray: '!bg-surface-gray-3 text-ink-gray-6',
}

const style = computed<NotificationItemStyle>(() => {
  const custom = props.itemStyle?.(props.notification)
  return {
    icon: custom?.icon ?? props.typeMeta?.icon,
    color: custom?.color ?? props.typeMeta?.color ?? 'gray',
    image: custom?.image,
    label: custom?.label,
  }
})

const colorClass = computed(() => COLOR_CLASS[style.value.color ?? 'gray'] || COLOR_CLASS.gray)

// fallback initials for the Avatar when there is no image/icon
const avatarLabel = computed(
  () => style.value.label ?? (props.notification.type || props.notification.from_user || '?').charAt(0),
)

// best-effort lucide class; for guaranteed icon rendering hosts can use the #leading slot.
// (frappe-ui renders lucide via `lucide-<name>` utility classes.)
const iconClass = computed(() => (style.value.icon ? `lucide-${style.value.icon} size-4` : ''))

const isUnread = computed(() => !props.notification.read)
const timeAgo = computed(() => dayjs(props.notification.creation as string).fromNow())
</script>

<template>
  <div
    class="flex gap-3 p-3 border-b last:border-0 cursor-pointer hover:bg-surface-gray-1"
    :class="{ 'bg-surface-gray-1/40': isUnread }"
    @click="emit('click', notification)"
  >
    <!-- leading visual: a frappe-ui Avatar by default; fully overridable via #leading -->
    <slot name="leading" :notification="notification" :style="style" :is-unread="isUnread">
      <Avatar
        :image="style.image"
        :label="avatarLabel"
        size="lg"
        :class="['mt-0.5 flex-shrink-0', colorClass]"
      >
        <template v-if="style.icon && !style.image" #default>
          <span :class="iconClass" />
        </template>
        <template v-if="isUnread" #indicator>
          <span class="size-2 rounded-full bg-surface-blue-3 ring-2 ring-surface-white" />
        </template>
      </Avatar>
    </slot>

    <!-- body -->
    <div class="min-w-0 flex-1">
      <div
        class="text-base leading-snug text-ink-gray-8 [&_b]:font-semibold"
        v-html="notification.subject"
      />
      <div class="mt-1 text-xs text-ink-gray-5">{{ timeAgo }}</div>
    </div>
  </div>
</template>
