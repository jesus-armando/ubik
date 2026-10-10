import type { NextConfig } from 'next';
import path from 'path';

const API_MOTOR_URL = process.env.P4_API_URL || 'http://localhost:8000';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  webpack: (config) => {
    config.resolve.alias['@'] = path.resolve(__dirname);
    return config;
  },
  // El asistente (POST /motor/analisis/<id>/chat) puede tardar si Gemini está saturado y
  // prueba otro modelo; el proxy de los rewrites corta a los 30 s por omisión.
  experimental: { proxyTimeout: 120_000 },
  // Recortes y video de los análisis subidos, y el asistente: /motor/... -> API del motor
  async rewrites() {
    return [{ source: '/motor/:path*', destination: `${API_MOTOR_URL}/:path*` }];
  },
};

export default nextConfig;
