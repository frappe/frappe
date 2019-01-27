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
    props: ['module_name'],
    data() {
        return {
            stats: {},
            sections: []
        }
    },
    created() {
        this.get_sections();
        this.get_stats();
    },
    updated() {
        frappe.app.update_notification_count_in_modules();
    },
    methods: {
        get_sections() {
            return frappe.call({
				method: "frappe.desk.moduleview.get",
				args: {
					module: this.module_name,
				},
				callback: (r) => {
                    var m = frappe.get_module(this.module_name);
                    this.sections = r.message.data;
                    this.process_data(this.module_name, this.sections);
                    // setTimeout(() => {}, 500);
				},
				freeze: true,
			});
        },
        get_stats() {
            //
        },
        process_data(module_name, data) {
            frappe.module_links[module_name] = [];
            console.log(data);
            data.forEach(function(section) {
                section.items.forEach(function(item) {
                    item.style = '';
                    if(item.type==="doctype") {
                        item.doctype = item.name;

                        // map of doctypes that belong to a module
                        frappe.module_links[module_name].push(item.name);
                    }
                    if(!item.route) {
                        if(item.link) {
                            item.route=strip(item.link, "#");
                        }
                        else if(item.type==="doctype") {
                            if(frappe.model.is_single(item.doctype)) {
                                item.route = 'Form/' + item.doctype;
                            } else {
                                if (item.filters) {
                                    frappe.route_options=item.filters;
                                }
                                item.route="List/" + item.doctype;
                                //item.style = 'font-weight: 500;';
                            }
                            // item.style = 'font-weight: bold;';
                        }
                        else if(item.type==="report" && item.is_query_report) {
                            item.route="query-report/" + item.name;
                        }
                        else if(item.type==="report") {
                            item.route="List/" + item.doctype + "/Report/" + item.name;
                        }
                        else if(item.type==="page") {
                            item.route=item.name;
                        }
                    }

                    if(item.route_options) {
                        item.route += "?" + $.map(item.route_options, function(value, key) {
                            return encodeURIComponent(key) + "=" + encodeURIComponent(value); }).join('&');
                    }

                    if(item.type==="page" || item.type==="help" || item.type==="report" ||
                    (item.doctype && frappe.model.can_read(item.doctype))) {
                        item.shown = true;
                    }
                });
            });
            console.log('2', data);
        }
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
