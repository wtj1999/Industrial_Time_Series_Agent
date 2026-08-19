var _a;
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
// In Docker, localhost points back to the frontend container. Use the
// Compose service name by default; local non-Docker runs can override this.
var proxyTarget = (_a = process.env.VITE_PROXY_TARGET) !== null && _a !== void 0 ? _a : 'http://backend:8000';
// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
    server: {
        port: 5173,
        host: true,
        proxy: {
            // Proxy API requests to the FastAPI backend
            '/api': {
                target: proxyTarget,
                changeOrigin: true,
                // Proxy timeouts need to be generous for long-running agent tasks
                timeout: 600000,
                proxyTimeout: 600000,
            },
            '/health': {
                target: proxyTarget,
                changeOrigin: true,
            },
        },
    },
});
