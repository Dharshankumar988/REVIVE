import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.revive.app",
  appName: "REVIVE",
  webDir: "out",
  server: {
    androidScheme: "https",
  },
};

export default config;
