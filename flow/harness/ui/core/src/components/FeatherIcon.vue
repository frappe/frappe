<script>
import { h, mergeProps } from 'vue'
import feather from 'feather-icons'

// icons feather lacks, drawn on its 24px grid
const extraIcons = {
  bot: {
    attrs: { xmlns: 'http://www.w3.org/2000/svg', viewBox: '0 0 24 24', class: 'feather feather-bot' },
    contents:
      '<rect x="3" y="7" width="18" height="14" rx="4.5"/><path d="M12 7V3.5"/><circle cx="9" cy="14" r=".5" fill="currentColor"/><circle cx="15" cy="14" r=".5" fill="currentColor"/>',
  },
  // lucide's palette (ISC)
  palette: {
    attrs: { xmlns: 'http://www.w3.org/2000/svg', viewBox: '0 0 24 24', class: 'feather feather-palette' },
    contents:
      '<path d="M12 22a1 1 0 0 1 0-20 10 9 0 0 1 10 9 5 5 0 0 1-5 5h-2.25a1.75 1.75 0 0 0-1.4 2.8l.3.4a1.75 1.75 0 0 1-1.4 2.8z"/><circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/>',
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
