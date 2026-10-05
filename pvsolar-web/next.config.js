/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Permite a imagem Docker copiar um servidor auto-contido (.next/standalone)
  output: 'standalone',
  images: {
    domains: ['localhost'],
  },
};

module.exports = nextConfig;
