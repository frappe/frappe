import { createApp } from 'vue'
import {
  Button,
  Input,
  TextInput,
  FormControl,
  ErrorMessage,
  Dialog,
  Alert,
  Badge,
  frappeRequest,
  setConfig,
  pageMetaPlugin,
  resourcesPlugin,
  useCall,
} from 'frappe-ui'
import router from './router'
import App from './App.vue'
import './index.css'

const globalComponents: Record<string, any> = {
  Button,
  TextInput,
  Input,
  FormControl,
  ErrorMessage,
  Dialog,
  Alert,
  Badge,
}

const app = createApp(App)

setConfig('resourceFetcher', frappeRequest)
app.use(resourcesPlugin)
app.use(pageMetaPlugin)
app.use(router)

for (const key in globalComponents) {
  app.component(key, globalComponents[key])
}

if (import.meta.env.DEV) {
  useCall({
    url: '/api/v2/method/{{ app_name }}.www.{{ frontend_route }}.get_context_for_dev',
    method: 'POST',
    onSuccess(values: Record<string, any>) {
      for (const key in values) {
        ;(window as any)[key] = values[key]
      }
      app.mount('#app')
    },
  })
} else {
  app.mount('#app')
}
