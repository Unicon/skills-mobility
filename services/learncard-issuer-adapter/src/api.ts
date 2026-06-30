import express, { type Express, type Request, type Response } from "express";
import { type IssuerConfig, isConfigured } from "./config";
import { issueCredential } from "./learncard";
import { logger } from "./logger";
import { toError, toSuccess } from "./resultmap";
import { IssueRequest } from "./schemas";

export function createApp(cfg: IssuerConfig): Express {
  const app = express();
  app.use(express.json({ limit: "1mb" }));

  app.get("/healthz", (_req: Request, res: Response) => {
    res.json({ status: "ok", configured: isConfigured(cfg) });
  });

  app.post("/internal/issue-learncard-badge", async (req: Request, res: Response) => {
    const parsed = IssueRequest.safeParse(req.body);
    if (!parsed.success) {
      res.status(422).json({
        status: "failed",
        external_reference_id: null,
        result: null,
        error: { message: "invalid request body", code: "invalid_request" },
      });
      return;
    }
    const { execution_id, payload } = parsed.data;
    logger.info("issue request received", { execution_id });
    try {
      const result = await issueCredential(cfg, payload.unsigned_vc);
      logger.info("credential issued", { execution_id, ref: result.externalReferenceId });
      res.json(toSuccess(result));
    } catch (err) {
      // A normalized failure envelope (not an HTTP error) — the router reads `status`.
      logger.error("issuance failed", { execution_id, error: String(err) });
      res.json(toError(err));
    }
  });

  return app;
}
