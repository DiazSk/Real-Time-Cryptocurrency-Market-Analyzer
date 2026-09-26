import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Keep the dev badge out of the product (and out of review screenshots).
  devIndicators: false,
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "assets.coingecko.com" },
      { protocol: "https", hostname: "coin-images.coingecko.com" },
    ],
  },
};

export default nextConfig;
