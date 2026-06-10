<script setup lang="ts">
import { computed } from 'vue'
import type { Component } from 'vue'
import { Avatar, FeatherIcon, dayjs } from 'frappe-ui'
import type { NotificationIcon, NotificationLog } from './types'

const props = defineProps<{
  notification: NotificationLog
  /** lucide/feather icon name (string) or a Component; omitted => sender avatar */
  icon?: NotificationIcon
}>()

const emit = defineEmits<{
  click: [n: NotificationLog]
}>()

// string => render via frappe-ui's icon component; Component => render directly;
// undefined => fall back to the sender's Avatar (the common case).
const iconName = computed(() => (typeof props.icon === 'string' ? props.icon : undefined))
const iconComponent = computed(() =>
  props.icon && typeof props.icon !== 'string' ? (props.icon as Component) : undefined,
)

// fallback initials for the Avatar when there is no sender image
const avatarLabel = computed(
  () => (props.notification.from_user || props.notification.type || '?').charAt(0),
)

const title = computed(() => props.notification.title ?? props.notification.subject ?? '')
const description = computed(() => props.notification.description ?? '')

const isUnread = computed(() => !props.notification.read)
const timeAgo = computed(() => dayjs(props.notification.creation as string).fromNow())
</script>

<template>
  <div
    class="flex gap-3 p-3 border-b last:border-0 cursor-pointer hover:bg-surface-gray-1"
    :class="{ 'bg-surface-gray-1/40': isUnread }"
    @click="emit('click', notification)"
  >
    <!-- leading visual: sender avatar by default; icon string/Component overrides it -->
    <div class="relative mt-0.5 flex-shrink-0">
      <component
        :is="iconComponent"
        v-if="iconComponent"
        :notification="notification"
      />
      <div
        v-else-if="iconName"
        class="flex size-8 items-center justify-center rounded-full bg-surface-gray-3 text-ink-gray-7"
      >
        <FeatherIcon :name="iconName" class="size-4" />
      </div>
      <Avatar
        v-else
        :image="notification.from_user_image"
        :label="avatarLabel"
        size="lg"
      />
      <span
        v-if="isUnread"
        class="absolute -right-0.5 -top-0.5 size-2 rounded-full bg-surface-blue-3 ring-2 ring-surface-white"
      />
    </div>

    <!-- body -->
    <div class="min-w-0 flex-1">
      <div
        class="text-base leading-snug text-ink-gray-8 [&_b]:font-semibold"
        v-html="title"
      />
      <div
        v-if="description"
        class="mt-0.5 text-sm leading-snug text-ink-gray-6 line-clamp-2"
        v-html="description"
      />
      <div class="mt-1 text-xs text-ink-gray-5">{{ timeAgo }}</div>
    </div>
  </div>
</template>
