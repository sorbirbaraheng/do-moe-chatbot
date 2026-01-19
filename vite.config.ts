import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  return {
    server: {
      port: 3001,
      host: '0.0.0.0',
      proxy: {
        // Proxy for Pinecone API to bypass CORS
        '/api/pinecone': {
          target: 'https://placeholder.pinecone.io', // Will be overridden by the actual request
          changeOrigin: true,
          secure: true,
          rewrite: (path) => path.replace(/^\/api\/pinecone/, ''),
          configure: (proxy, options) => {
            proxy.on('proxyReq', (proxyReq, req, res) => {
              // Extract the target Pinecone host from the custom header
              const pineconeHost = req.headers['x-pinecone-host'] as string;
              if (pineconeHost) {
                const targetUrl = new URL(pineconeHost.startsWith('https://') ? pineconeHost : `https://${pineconeHost}`);
                (options as any).target = targetUrl.origin;
                proxyReq.setHeader('Host', targetUrl.host);
              }
            });
          }
        }
      }
    },
    plugins: [react()],
    define: {
      'process.env.API_KEY': JSON.stringify(env.GEMINI_API_KEY),
      'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY)
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      }
    }
  };
});
