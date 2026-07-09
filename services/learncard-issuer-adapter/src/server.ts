import { createApp } from "./api";
import { isConfigured, loadConfig } from "./config";
import { installCrashGuards } from "./guards";
import { logger } from "./logger";

installCrashGuards();

const cfg = loadConfig();
createApp(cfg).listen(cfg.port, () => {
  logger.info("learncard-issuer-adapter listening", {
    port: cfg.port,
    configured: isConfigured(cfg),
  });
});
