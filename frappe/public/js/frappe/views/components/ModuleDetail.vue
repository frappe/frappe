<template>
    <div class="sections-container">
        <div v-for="section in sections"
            :key="section.name"
            class="border section-box"
        >
            <h4 class="h4"> {{ section.label }} </h4>
            <p v-for="item in section.items" class="small"
                :key="item.name"
                :data-youtube-id="item.type==='help' ? item.youtube_id : false"
            >
                <a :href="item.route">{{ item.label || __(item.name) }}</a>
                <span class="open-notification global hide"
                    @click="item.doctype || item.name ? frappe.ui.notifications.show_open_count_list(item.doctype || item.name) : false"
                    :data-doctype="item.doctype || item.name"></span>
            </p>
        </div>
    </div>
</template>

<script>
export default {
    props: ['module_name', 'sections'],
    updated() {
        frappe.app.update_notification_count_in_modules();
    }
}
</script>
<style lang="less" scoped>
.sections-container {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    column-gap: 15px;
    row-gap: 15px;
}

.section-box {
    padding: 10px 20px;
    border-radius: 4px;

    p {
        line-height: 1.5em;
    }
}

.h4 {
    margin-bottom: 15px;
}

a:hover, a:focus {
    text-decoration: underline;
}

</style>
