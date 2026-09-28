# Tag

`Tag` renders one labeled tag. Its `color` is a color name stored on the Frappe
Tag document; an absent or unknown value renders gray without changing stored data.

```vue
<Tag label="Urgent" color="Red">
  <template #suffix>
    <button aria-label="Remove Urgent"><LucideX class="size-3" /></button>
  </template>
</Tag>
```

`TagPicker` loads app-visible tags, lets the user search, create with a palette
color, select, and remove. It saves one batch when the picker closes. The host
supplies the document identity, app name, and current comma-separated
`_user_tags` value:

```vue
<TagPicker
  doctype="HD Ticket"
  :docname="ticket.name"
  app="helpdesk"
  :tags="ticket._user_tags"
  @update:tags="ticket._user_tags = $event"
/>
```

Tags are globally named. Their app memberships are shared, so adding an app to
an existing Desk tag keeps its Desk membership. A tag can have one shared color
across all its apps. Existing unscoped tags are treated as Desk tags.
