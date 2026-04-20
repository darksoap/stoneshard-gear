// @ts-check
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';
import fs from 'fs';
import path from 'path';

function excludePngPlugin() {
  return {
    name: 'exclude-png',
    writeBundle() {
      function deletePngFiles(dir) {
        if (!fs.existsSync(dir)) return;
        const files = fs.readdirSync(dir);
        for (const file of files) {
          const filePath = path.join(dir, file);
          const stat = fs.statSync(filePath);
          if (stat.isDirectory()) {
            deletePngFiles(filePath);
          } else if (file.endsWith('.png')) {
            fs.unlinkSync(filePath);
          }
        }
      }
      
      deletePngFiles('./dist/images');
    }
  };
}

export default defineConfig({
  site: 'https://darksoap.github.io',
  base: process.env.NODE_ENV === 'production' ? '/stoneshard-gear' : '/',
  vite: {
    plugins: [tailwindcss(), excludePngPlugin()],
  },
});
