import { defineConfig } from 'wxt';

// WXT generates manifest.json from this config + the files in entrypoints/.
export default defineConfig({
  modules: ['@wxt-dev/module-react'],
  manifest: {
    name: 'whoknows',
    version: '0.1.0',
    description:
      'Expertise finds you, not the other way around. Shows which colleagues can help when you hesitate while writing.',
    permissions: ['storage'],
    host_permissions: ['http://127.0.0.1:8000/*', 'http://localhost:8000/*'],
    action: { default_title: 'whoknows' },
  },
  webExt: {
    startUrls: ['http://127.0.0.1:8000/demo/mail.html', 'https://mail.google.com'],
    // Keep a persistent dev profile so you stay logged in to Gmail between runs.
    chromiumArgs: ['--user-data-dir=./.wxt/chrome-data'],
  },
});
