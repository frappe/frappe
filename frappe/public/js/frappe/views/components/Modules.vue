<template>
    <div class="modules-page-container">
        <module-detail v-if="this.route && modules_list.map(m => m.module_name).includes(route[1])" :module_name="route[1]" :sections="current_module_sections"></module-detail>
    </div>
</template>

<script>
import ModuleDetail from './ModuleDetail.vue';

export default {
    components: {
        ModuleDetail
    },
    data() {
        return {
            route: frappe.get_route(),
            current_module_label: '',
            current_module_sections: [], 
            modules_data_cache: {},
            modules_list: [],
        };
    },
    created() {
        this.get_modules_list();
        this.update_current_module();
    },
    mounted() {
        frappe.module_links = {};
        frappe.route.on('change', () => {
            this.update_current_module();
        });
    },
    methods: {
        update_current_module() {
            let route = frappe.get_route();
            if(route[0] === 'modules' || !route[0]) {
                this.route = route;
                let module_name = route[1];
                let title = this.current_module_label ? this.current_module_label : module_name;
                title = module_name!=='home' ? title : 'Modules';

                frappe.modules.home && frappe.modules.home.page.set_title(title);

                if(module_name) {
                    this.get_module_sections(module_name);
                }
            }
        },

        get_modules_list() {
            let res = frappe.call({
                method: 'frappe.desk.doctype.desktop_icon.desktop_icon.get_modules_from_all_apps',
            });

            res.then(r => {
                if (r.message) {
                    let modules_list = r.message;

                    this.modules_list = modules_list
                        .filter(d => (d.type==='module' || d.category==='Places') && !d.blocked);
                }
            });
        },

        get_module_sections(module_name) {
            let cache = this.modules_data_cache[module_name];
            if(cache) {
                this.current_module_sections = cache;
            } else {
                return frappe.call({
                    method: "frappe.desk.moduleview.get",
                    args: {
                        module: module_name,
                    },
                    callback: (r) => {
                        var m = frappe.get_module(module_name);
                        this.current_module_sections = r.message.data;
                        this.process_data(module_name, this.current_module_sections);
                        this.modules_data_cache[module_name] = this.current_module_sections;
                    },
                    freeze: true,
                });
            }
        },
        process_data(module_name, data) {
            frappe.module_links[module_name] = [];
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

                        item.route = '#' + item.route;
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
        }
    }
}
</script>

<style lang="less" scoped>
.modules-page-container {
    margin: 70px 85px;
}

.module-category {    
    margin-top: 30px;
    margin-bottom: 15px;
    border-bottom: 1px solid #d0d8dd;
}

.modules-container {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    column-gap: 15px;
    row-gap: 15px;
}

.module-box {
    border-radius: 4px;
    cursor: pointer;
    padding: 5px 0px;
    display: block;
}

.module-box:hover {
    background-color: #fafbfc;
}

.module-box-content {
    padding-right: 15px;
    flex: 1;

    h4 {
        margin-bottom: 5px
    }

    p {
        margin-top: 5px;
        font-size: 80%;
    }
}

.icon-box {
    padding: 15px;
    width: 54px;
    display: flex;
    justify-content: center;
}

.icon {
    font-size: 24px;
}

</style>
