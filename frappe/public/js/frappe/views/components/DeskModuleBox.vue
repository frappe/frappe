<template>
  <div
    v-if="!hidden"
    class="border module-box"
    :class="{ 'hovered-box': hovered }"
    :draggable="true"
    @dragstart="on_dragstart"
    @dragend="on_dragend"
    @dragenter="on_enter"
    @drop="on_drop"
  >
    <div class="flush-top">
      <div class="module-box-content">
        <div class="level">
          <a class="module-box-link" :href="type === 'module' ? '#modules/' + module_name : link">
            <h4 class="h4">
              <div>
                <i :class="iconClass" style="color:#8d99a6;font-size:18px;margin-right:6px;"></i>
                {{ label }}
              </div>
            </h4>
          </a>
          <dropdown v-if="links && links.length" :items="links">
            <span class="pull-right">
              <i class="octicon octicon-chevron-down"></i>
            </span>
          </dropdown>
          <!-- <span class="drag-handle octicon octicon-three-bars text-extra-muted"></span> -->
        </div>
        <!-- <p v-if="links && links.length" class="small text-muted">
          <a
            v-for="shortcut in links"
            :key="(shortcut.name || shortcut.label) + shortcut.type"
            :href="shortcut.route"
            class="btn btn-default btn-xs shortcut-tag"
            title="toggle Tag"
            >{{ shortcut.label }}</a
          >
        </p>-->
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
    iconClass() {
      if (this.icon) {
        return this.icon;
      } else {
        return "octicon octicon-file-text";
      }
    }
  },
  methods: {
    on_dragstart() {
      this.$emit("box-dragstart", this.index);
      return 0;
    },
    on_dragend() {
      this.$emit("box-dragend", this.index);
      return 0;
    },
    on_enter() {
      this.$emit("box-enter", this.index);
      // this.hovered = 1;
    },
    on_drop() {
      this.$emit("box-drop", this.index);
    },
    on_exit() {
      // this.hovered = 0;
    }
  }
};
</script>

<style lang="less" scoped>
.module-box {
  border-radius: 4px;
  padding: 5px 15px;
  display: block;
  background-color: #ffffff;
}

.module-box:hover {
  box-shadow: 0 3px 4px 0 rgba(18, 18, 19, 0.08);
}

.hovered-box {
  background-color: #fafbfc;
}

.octicon-chevron-down {
  font-size: 24px;
  padding: 5px;
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
