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
    const { workflow_id, execution_id, step_id, correlation_id, payload } = parsed.data;
    // Attach all four correlation identifiers to every log line (FR-LCI-11) — the
    // failure path especially must be correlatable back to the workflow/step.
    const ids = { workflow_id, execution_id, step_id, correlation_id };
    logger.info("issue request received", ids);
    try {
      const result = await issueCredential(cfg, payload.unsigned_vc);
      logger.info("credential issued", { ...ids, ref: result.externalReferenceId });
      res.json(toSuccess(result));
    } catch (err) {
      // A normalized failure envelope (not an HTTP error) — the router reads `status`.
      logger.error("issuance failed", { ...ids, error: String(err) });
      res.json(toError(err));
    }
  });

  return app;
}
