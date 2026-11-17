import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  base: process.env.BASE_PATH || "/",
  plugins: [
    VitePWA({
      registerType: "autoUpdate",
      manifest: {
        name: "대한민국 팩트 대시보드",
        short_name: "팩트 대시보드",
        description: "공적 자료로 보는 대한민국 민주주의·자유 지표",
        lang: "ko",
        theme_color: "#1f4e8c",
        background_color: "#ffffff",
        display: "standalone",
        icons: [
          { src: "icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icon-512.png", sizes: "512x512", type: "image/png", purpose: "any maskable" },
        ],
      },
      workbox: {
        // 데이터는 최신을 우선, 오프라인이면 캐시 사용
        runtimeCaching: [{ urlPattern: /\/data\/.*\.json$/, handler: "NetworkFirst", options: { cacheName: "data" } }],
        globIgnores: ["**/data/**"],
      },
    }),
  ],
});
