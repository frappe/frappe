<template>
    <div class="flex justify-end gap-4 items-center">
        <slot name="customControls"><div></div></slot>
        <div class="flex gap-2">
            <div v-if="config_updated"
                class="flex items-center gap-2 border-r pr-2"
            >
                <Button :label="'Cancel'" @click="cancelChanges"/>
                <Button :label="'Save Changes'" @click="saveChanges"/>
            </div>
            <template v-if="options.showColumnSettings">
                <ListColumnSettings v-model="config.columns" :allColumns="config.allColumns"/>
            </template>
        </div>
    </div>
</template>

<script setup>
import { ref, watch, computed, defineEmits, defineModel  } from 'vue';
import ListColumnSettings from '@/components/ListColumnSettings.vue';

const emit = defineEmits(['updateConfigSettings']);

const config = defineModel();
const oldConfig = ref({});

const props = defineProps({
    options: {
        type: Object,
        default: {}
    }
});

watch(
    config,
    (config) => {
        if (!config) return;
        oldConfig.value = JSON.parse(JSON.stringify(config));
    },
    { immediate: true }
);

const config_updated = computed(() => JSON.stringify(oldConfig.value) != JSON.stringify(config.value));

const saveChanges = () => {
    emit('updateConfigSettings');
}

const cancelChanges = () => {
    config.value = JSON.parse(JSON.stringify(oldConfig.value));
}
</script>