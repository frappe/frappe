import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'node:path'
import frappeui from 'frappe-ui/vite'

export default defineConfig({
  plugins: [
    frappeui({
      frontendRoute: '/{{ frontend_route }}',
      frappeTypes: {
        input: {
          frappe: ['todo'],
        },
      },
    }),
    vue(),
  ],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      'tailwind.config.js': resolve(__dirname, 'tailwind.config.js'),
    },
  },
  optimizeDeps: {
    include: ['tailwind.config.js'],
  },
})
