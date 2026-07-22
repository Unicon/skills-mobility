import { logger } from "./logger";

/**
 * Keep the long-running adapter alive when a *detached* promise rejects.
 *
 * During network wallet init the LearnCard SDK fires background handshakes
 * against LearnCloud (e.g. `utilities.getChallenges`). When LearnCloud returns
 * a 500, that rejection is not in our await chain — the issuance path in
 * `api.ts` is already try/caught and turns failures into a normalized error
 * envelope — so Node's default `unhandledRejection` behavior would terminate
 * the whole process. A single vendor background failure must not take the
 * adapter down; log it and continue serving.
 */
export function installCrashGuards(): void {
  process.on("unhandledRejection", (reason) => {
    logger.warn("unhandled promise rejection (kept alive)", { reason: String(reason) });
  });
}
