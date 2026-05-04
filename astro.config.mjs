// @ts-check
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';

const isProd = /** @type {any} */ (process).env.NODE_ENV === 'production';

export default defineConfig({
  site: 'https://darksoap.github.io',
  base: isProd ? '/stoneshard-gear' : '/',
  prefetch: {
    prefetchAll: false,
    defaultStrategy: 'hover',
  },
  vite: {
    plugins: [tailwindcss()],
  },
});
