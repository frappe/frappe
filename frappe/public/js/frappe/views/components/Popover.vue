<template>
  <div
    class="inline-block relative"
    :class="{ 'w-full': this.fullwidth }"
    v-on-outside-click="closePopover"
  >
    <div @click="togglePopover">
      <slot :togglePopover="togglePopover" :closePopover="closePopover"></slot>
    </div>
    <div
      v-show="isOpen"
      class="absolute mt-default z-20"
      :class="popoverClasses"
    >
      <slot name="popover-content"></slot>
    </div>
  </div>
</template>
<script>
export default {
  name: 'Popover',
  props: {
    align: {
      default: 'left',
    },
    fullwidth: {
      default: false,
    },
  },
  data() {
    return {
      isOpen: false,
    }
  },
  computed: {
    popoverClasses() {
      return {
        'pin-r': this.align === 'right',
        'pin-l': this.align === 'left',
        'w-full': this.fullwidth === true,
      }
    },
  },
  methods: {
    togglePopover() {
      this.isOpen = !this.isOpen
    },
    closePopover() {
      this.isOpen = false
    },
  },
}
</script>
<style scoped>
.relative {
  position: relative;
}
.inline-block {
  display: inline-block;
}
.w-full {
  width: 100%;
}
.pin-r {
  right: 0;
}
.pin-l {
  left: 0;
}
.absolute {
  position: absolute;
}
.mt-default {
  margin-top: 20px;
}
.z-20 {
  z-index: 20;
}
</style>
