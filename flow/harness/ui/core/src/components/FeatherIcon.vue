<script>
import { h, mergeProps } from 'vue'
import feather from 'feather-icons'

// icons feather lacks, drawn on its 24px grid
const extraIcons = {
  bot: {
    attrs: { xmlns: 'http://www.w3.org/2000/svg', viewBox: '0 0 24 24', class: 'feather feather-bot' },
    contents:
      '<rect x="4" y="8" width="16" height="12" rx="2"/><path d="M12 8V5"/><circle cx="12" cy="4" r="1"/><path d="M2 14h2M20 14h2M9 13v2M15 13v2"/>',
  },
}
const validIcons = [...Object.keys(feather.icons), ...Object.keys(extraIcons)]

export default {
  props: {
    name: {
      type: String,
      required: true,
      validator(value) {
        const valid = validIcons.includes(value)
        if (!valid) {
          console.groupCollapsed(
            '[frappe-ui] name property for feather-icon must be one of ',
          )
          console.dir(validIcons)
          console.groupEnd()
        }
        return valid
      },
    },
    color: {
      type: String,
      default: null,
    },
    strokeWidth: {
      type: Number,
      default: 1.5,
    },
  },
  render() {
    let icon = feather.icons[this.name] || extraIcons[this.name]
    if (!icon) {
      icon = feather.icons['circle']
    }
    return h(
      'svg',
      mergeProps(
        icon.attrs,
        {
          fill: 'none',
          stroke: 'currentColor',
          color: this.color,
          'stroke-linecap': 'round',
          'stroke-linejoin': 'round',
          'stroke-width': this.strokeWidth,
          width: null,
          height: null,
          class: [icon.attrs.class, 'shrink-0'],
          innerHTML: icon.contents,
        },
        this.$attrs,
      ),
    )
  },
}
</script>
