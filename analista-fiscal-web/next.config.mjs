import withBundleAnalyzerInit from "@next/bundle-analyzer";

const withBundleAnalyzer = withBundleAnalyzerInit({
  enabled: process.env.ANALYZE === "1",
});

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Marco 4 PR4 (#15): build de produção self-contained para a imagem Docker
  // (.next/standalone/server.js). Sem isto a imagem precisaria do node_modules
  // inteiro + `next start`. Inerte em `next dev`.
  output: "standalone",
  experimental: {
    reactCompiler: process.env.NODE_ENV === "production",
  },
};

export default withBundleAnalyzer(nextConfig);
