import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      {
        source: "/",
        destination: "/perm",
        permanent: true,
      },
    ];
  },
  images: {
    remotePatterns: [
      new URL("https://picsum.photos/**"),
      new URL("https://quizplease.ru/**"),
      new URL("https://mozgoboynya.ru/**"),
    ],
  },
};

export default nextConfig;
