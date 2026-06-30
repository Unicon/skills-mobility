import { createApp } from "./api";
import { isConfigured, loadConfig } from "./config";
import { logger } from "./logger";

const cfg = loadConfig();
createApp(cfg).listen(cfg.port, () => {
  logger.info("learncard-issuer-adapter listening", {
    port: cfg.port,
    configured: isConfigured(cfg),
  });
});
