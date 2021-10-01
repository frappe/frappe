<template>
  <div class="inline-block relative" :class="{ 'w-full': this.fullwidth }" v-outside="closePopover">
    <div @click="togglePopover">
      <slot :togglePopover="togglePopover" :closePopover="closePopover"></slot>
    </div>
    <div v-show="isOpen" class="absolute mt-default z-20" :class="popoverClasses">
      <slot name="popover-content"></slot>
    </div>
  </div>
</template>
<script>
let instances = [];

function onDocumentClick(e, el, fn) {
  let target = e.target;
  if (el !== target && !el.contains(target)) {
    fn(e);
  }
}

export default {
  name: "Popover",
  props: {
    align: {
      default: "left"
    },
    fullwidth: {
      default: false
    }
  },
  data() {
    return {
      isOpen: false
    };
  },
  directives: {
    outside: {
      bind(el, binding) {
        el.dataset.outsideClickIndex = instances.length;

        const fn = binding.value;
        const click = function(e) {
          onDocumentClick(e, el, fn);
        };

        document.addEventListener("click", click);
        instances.push(click);
      },
      unbind(el) {
        const index = el.dataset.outsideClickIndex;
        const handler = instances[index];
        document.addEventListener("click", handler);
        instances.splice(index, 1);
      }
    }
  },
  computed: {
    popoverClasses() {
      return {
        "pin-r": this.align === "right",
        "pin-l": this.align === "left",
        "w-full": this.fullwidth === true
      };
    }
  },
  methods: {
    togglePopover() {
      this.isOpen = !this.isOpen;
    },
    closePopover() {
      this.isOpen = false;
    }
  }
};
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
  margin-top: 25px;
}
.z-20 {
  z-index: 20;
}
</style>
