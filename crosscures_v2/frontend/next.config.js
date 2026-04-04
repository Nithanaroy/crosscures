/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    serverActions: {},
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    NEXT_PUBLIC_CARTESIA_API_KEY: process.env.NEXT_PUBLIC_CARTESIA_API_KEY || '',
    NEXT_PUBLIC_CARTESIA_VERSION: process.env.NEXT_PUBLIC_CARTESIA_VERSION || '2026-03-01',
    NEXT_PUBLIC_CARTESIA_VOICE_ID: process.env.NEXT_PUBLIC_CARTESIA_VOICE_ID || '694f9389-aac1-45b6-b726-9d9369183238',
  },
}

module.exports = nextConfig
