<template>
  <Popover :align="align">
    <slot></slot>
    <ul slot="popover-content" class="list-reset border">
      <li v-for="item of dropdownItems" :key="item.label" :class="item.class || null">
        <a v-if="item.route" class="list-item" :href="item.route">{{ item.label }}</a>
        <div v-else class="list-item" @click="item.action">{{ item.label }}</div>
      </li>
    </ul>
  </Popover>
</template>
<script>
import Popover from "./Popover.vue";

export default {
  name: "Dropdown",
  components: {
    Popover
  },
  props: {
    items: {
      type: Array,
      default: () => []
    },
    label: {
      type: String,
      default: "Dropdown"
    },
    align: {
      type: String,
      default: "right"
    }
  },
  data() {
    return {
      isOpen: false
    };
  },
  computed: {
    dropdownItems() {
      return (this.items || []).map(item => {
        if (typeof item === "string") {
          return {
            label: item,
            action: console.log
          };
        }
        if (!item.action && item.route) {
          item.action = this.setRoute.bind(this, item.route);
        }
        return item;
      });
    }
  },
  methods: {
    setRoute(route) {
      this.$router.push(route);
    }
  }
};
</script>
<style scoped>
.list-reset {
  list-style: none;
  padding: 0;
  cursor: pointer;
  background-color: #fff;
  width: 16rem;
  box-shadow: 0 4px 8px 0 rgba(0, 0, 0, 0.12), 0 2px 4px 0 rgba(0, 0, 0, 0.08);
  border-bottom-right-radius: 0.25rem;
  border-bottom-left-radius: 0.25rem;
}
.list-item:hover {
  background-color: #f0f4f7;
}
.list-item {
  padding: 14px;
  transition: all 0.1s ease-in;
}
a {
  font-size: 12px;
  text-decoration: none;
}
</style>
