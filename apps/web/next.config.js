const path = require("path");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Pin workspace root so Next.js does not pick up C:\Users\User\package-lock.json
  outputFileTracingRoot: path.join(__dirname, "../.."),
};

module.exports = nextConfig;
