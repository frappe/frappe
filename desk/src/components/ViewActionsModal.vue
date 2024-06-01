<template>
    <Dialog v-model="show" :options="{
        title: ` ${mode} View `,
        actions: [
            {
                label: mode,
                variant: 'solid',
                onClick: () => {
                    if (mode == 'Create')
                        createView()
                    else if (mode == 'Save')
                        renameView()
                    else
                        deleteView()
                },
            },
        ],
        size: 'sm'
    }">
        <template #body-content>
            <template v-if="mode == 'Create'">
                <FormControl :type="'text'" size="md" variant="subtle" label="View Name" v-model="newViewName" />
            </template>
            <template v-else-if="mode == 'Save'">
                <FormControl :type="'text'" size="md" variant="subtle" label="View Name"
                    v-model="config_settings.data.label" />
            </template>
            <template v-else>
                <div class="text-base">
                    Are you sure you want to delete this view?
                </div>
            </template>
        </template>
    </Dialog>
</template>

<script setup>
import { ref, defineModel } from 'vue';
import { useRoute } from 'vue-router';
import { Dialog, FormControl, createResource, call } from 'frappe-ui';

import { config_name, config_settings } from '@/stores/view';

const show = defineModel();

const props = defineProps({
    listConfig: {
        type: Object,
        required: true,
    },
    mode: {
        type: String,
        default: 'Create',
    }
});

const route = useRoute();

const newViewName = ref('');

const createConfigResource = createResource({
    url: 'frappe.client.insert',
    method: 'POST',
    makeParams: () => {
        return {
            doc: {
                doctype: 'View Config',
                document_type: route.params.doctype,
                label: newViewName.value,
                columns: JSON.stringify(props.listConfig.columns),
                filters: JSON.stringify(props.listConfig.filters),
                sort_field: props.listConfig.sort[0],
                sort_order: props.listConfig.sort[1]
            }
        }
    }
});

const createView = async () => {
    show.value = false;
    let doc = await createConfigResource.submit();
}

const deleteView = async () => {
    show.value = false;
    await call('frappe.client.delete', { doctype: "View Config", name: config_name.value });
}

const renameView = async () => {
    show.value = false;
    await call('frappe.client.set_value', {
        doctype: "View Config",
        name: config_name.value,
        fieldname: "label",
        value: config_settings.data.label
    });
}
</script>