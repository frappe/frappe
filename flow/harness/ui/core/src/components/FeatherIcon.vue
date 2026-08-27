<script>
import { h, mergeProps } from 'vue'
import feather from 'feather-icons'

const validIcons = Object.keys(feather.icons)

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
    let icon = feather.icons[this.name]
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
