<template>
  <!-- Subject and To are shown when enabled by props; Cc/Bcc are revealed by
		 the header toggles. The To row rides along so the sender can see and edit
		 who the reply goes to. -->
  <div class="px-2.5">
    <Row v-if="showSubject || subject" label="Subject">
      <input
        v-model="subject"
        type="text"
        class="flex-1 border-0 bg-transparent p-0 text-base text-ink-gray-8 placeholder-ink-gray-4 focus:ring-0"
        placeholder="Subject"
      />
    </Row>

    <Row label="To">
      <RecipientSelect v-model="model.to" class="flex-1" :search="search" />
    </Row>

    <Row v-if="showCc || model.cc.length" label="CC">
      <RecipientSelect v-model="model.cc" class="flex-1" :search="search" />
    </Row>

    <Row v-if="showBcc || model.bcc.length" label="BCC">
      <RecipientSelect v-model="model.bcc" class="flex-1" :search="search" />
    </Row>
  </div>
</template>

<script setup lang="ts">
import RecipientSelect from "./RecipientSelect.vue";
import Row from "./RecipientRow.vue";
import type { Recipients, RecipientSearch } from "../types";

defineProps<{
  showSubject?: boolean;
  showCc?: boolean;
  showBcc?: boolean;
  search?: RecipientSearch;
}>();
const model = defineModel<Recipients>({ required: true });
const subject = defineModel<string>("subject", { default: "" });
</script>
