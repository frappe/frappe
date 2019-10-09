<template>
  <div class="modules-page-container">
    <module-detail
      v-if="
        this.route && modules_list.map(m => m.module_name).includes(route[1])
      "
      :module_name="route[1]"
      :sections="current_module_sections"
    ></module-detail>
  </div>
</template>

<script>
import ModuleDetail from './ModuleDetail.vue'
import { generate_route } from './utils.js'

export default {
  components: {
    ModuleDetail,
  },
  data() {
    return {
      route: frappe.get_route(),
      current_module_label: '',
      current_module_sections: [],
      modules_data_cache: {},
      modules_list: frappe.boot.allowed_modules.filter(
        d => (d.type === 'module' || d.category === 'Places') && !d.blocked
      ),
    }
  },
  created() {
    this.update_current_module()
  },
  mounted() {
    frappe.module_links = {}
    frappe.route.on('change', () => {
      this.update_current_module()
    })
  },
  methods: {
    update_current_module() {
      let route = frappe.get_route()
      if (route[0] === 'modules') {
        this.route = route
        let module = this.modules_list.filter(m => m.module_name == route[1])[0]
        let module_name = module && (module.label || module.module_name)
        let title = this.current_module_label
          ? this.current_module_label
          : module_name

        frappe.modules.home && frappe.modules.home.page.set_title(title)

        if (!frappe.modules.home) {
          setTimeout(() => {
            frappe.modules.home.page.set_title(title)
          }, 200)
        }

        if (module_name) {
          this.get_module_sections(module.module_name)
        }
      }
    },

    get_module_sections(module_name) {
      let cache = this.modules_data_cache[module_name]
      if (cache) {
        this.current_module_sections = cache
      } else {
        this.current_module_sections = []
        return frappe.call({
          method: 'frappe.desk.moduleview.get',
          args: {
            module: module_name,
          },
          callback: r => {
            var m = frappe.get_module(module_name)
            this.current_module_sections = r.message.data
            this.process_data(module_name, this.current_module_sections)
            this.modules_data_cache[module_name] = this.current_module_sections
          },
          freeze: true,
        })
      }
    },
    process_data(module_name, data) {
      frappe.module_links[module_name] = []
      data.forEach(function(section) {
        section.items.forEach(function(item) {
          item.route = generate_route(item)
        })
      })
    },
  },
}
</script>

<style lang="less" scoped>
.modules-page-container {
  margin: 15px 0px;
}
</style>
