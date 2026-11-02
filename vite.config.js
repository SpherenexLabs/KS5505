import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import babel from '@rolldown/plugin-babel'

const projectRoot = path.dirname(fileURLToPath(import.meta.url))
const keyPath = path.join(projectRoot, 'certs', 'dev-key.pem')
const certPath = path.join(projectRoot, 'certs', 'dev-cert.pem')

// Browsers only give a page GPS on a secure origin. localhost counts as one, a
// plain http:// LAN address does not, so the patient's phone never sees the
// location prompt until the dev server speaks HTTPS. Generate the certificate
// with scripts\make-cert.ps1; without it the server falls back to HTTP.
const httpsCert =
  fs.existsSync(keyPath) && fs.existsSync(certPath)
    ? { key: fs.readFileSync(keyPath), cert: fs.readFileSync(certPath) }
    : undefined

if (!httpsCert) {
  console.warn(
    '\n[carebot] No dev certificate found, serving over HTTP.\n' +
      '[carebot] Phone location tracking needs HTTPS. Run:\n' +
      '[carebot]   powershell -ExecutionPolicy Bypass -File scripts\\make-cert.ps1\n',
  )
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    babel({ presets: [reactCompilerPreset()] })
  ],
  server: {
    // The patient opens the tracking link on their phone, so the dev server has
    // to answer on the LAN address and not only on localhost.
    host: true,
    // Fail loudly instead of sliding onto 5174. A second dev server on another
    // port still serves the dashboard, but the tracking link the backend hands
    // out points at 5173, so the phone would open a page that is not there.
    strictPort: true,
    https: httpsCert,
    // A Cloudflare quick tunnel arrives with a random *.trycloudflare.com Host
    // header, which Vite blocks by default as a DNS-rebinding guard.
    allowedHosts: ['.trycloudflare.com'],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
    },
  },
})
