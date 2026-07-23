/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ['antd', '@ant-design/icons'],
  output: 'standalone',
  async rewrites() {
    const backend = process.env.BACKEND_INTERNAL_URL || 'http://localhost:8000';
    return [{
      source: '/api/v1/:path*',
      destination: `${backend}/api/v1/:path*`,
    }];
  },
};

module.exports = nextConfig;
