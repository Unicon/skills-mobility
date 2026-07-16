import { createApp } from "./api";
import { isConfigured, loadConfig } from "./config";
import { installCrashGuards } from "./guards";
import { logger } from "./logger";

// Load .env when present (local dev; npm scripts run from the service dir) so
// SECURE_SEED / PROFILE_ID / PROFILE_NAME reach loadConfig(). In Docker the env
// is set directly and there is no .env — an absent file is fine.
try {
  process.loadEnvFile();
} catch {
  // no .env file — configuration comes from the environment
}

installCrashGuards();

const cfg = loadConfig();
createApp(cfg).listen(cfg.port, () => {
  logger.info("learncard-issuer-adapter listening", {
    port: cfg.port,
    configured: isConfigured(cfg),
  });
});
