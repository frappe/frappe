<template>
  <div
    v-if="!hidden"
    class="border module-box"
    :class="{ 'hovered-box': hovered }"
	:data-module-name="module_name"
  >
    <div class="flush-top">
      <div class="module-box-content">
        <div class="level">
          <a class="module-box-link" :href="type === 'module' ? '#modules/' + module_name : link">
            <h4 class="h4">
              <div>
                <i :class="icon_class" style="color:#8d99a6;font-size:18px;margin-right:6px;"></i>
                {{ label }}
              </div>
            </h4>
          </a>
          <dropdown v-if="dropdown_links && dropdown_links.length" :items="dropdown_links">
            <span class="pull-right">
              <i class="octicon octicon-chevron-down text-muted"></i>
            </span>
          </dropdown>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Dropdown from "./Dropdown.vue";

export default {
  props: [
    "index",
    "name",
    "label",
    "category",
    "type",
    "module_name",
    "link",
    "count",
    "onboard_present",
    "links",
    "description",
    "hidden",
    "icon"
  ],
  components: {
    Dropdown
  },
  data() {
    return {
      hovered: 0
    };
  },
  computed: {
    icon_class() {
      if (this.icon) {
        return this.icon;
      } else {
        return "octicon octicon-file-text";
      }
	},
	dropdown_links() {
		return this.type === 'module' ? this.links
			.filter(link => !link.hidden)
			.concat([
				{ label: __('Customize'), action: () => this.$emit('customize'), class: 'border-top' }
			]) : [];
	}
  },
};
</script>

<style lang="less" scoped>
@import "frappe/public/less/variables";

.module-box {
  border-radius: 4px;
  padding: 5px 15px;
  display: block;
  background-color: #ffffff;
}

.module-box.sortable-chosen {
	background-color: @disabled-background;
	border-color: @disabled-background;
}

.modules-container:not(.dragging) .module-box:hover {
	border-color: @text-muted;
}

.hovered-box {
  background-color: @light-bg;
}

.octicon-chevron-down {
  font-size: 14px;
  padding: 4px 6px 2px 6px;
  border-radius: 4px;

  &:hover {
	background: @btn-bg;
  }
}

.octicon-chevron-down:hover {
  cursor: pointer;
}

.module-box-content {
  width: 100%;

  p {
    margin-top: 5px;
    font-size: 80%;
    display: flex;
    overflow: hidden;
  }
}

.module-box-link {
  flex: 1;
  padding-top: 5px;
  padding-bottom: 5px;
  text-decoration: none;
  --moz-text-decoration-line: none;
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

.open-notification {
  top: -2px;
}

.shortcut-tag {
  margin-right: 5px;
}

.drag-handle {
  font-size: 12px;
}
</style>
