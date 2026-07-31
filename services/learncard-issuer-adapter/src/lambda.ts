// AWS Lambda entrypoint: wraps the same Express app that serves locally behind
// a Function URL via serverless-http (the Node analogue of the Python services'
// Mangum handlers — synchronous HTTP demo topology). Env comes from the Lambda
// configuration; there is no .env in the image.
import serverless from "serverless-http";

import { createApp } from "./api";
import { loadConfig } from "./config";
import { installCrashGuards } from "./guards";

installCrashGuards();

export const handler = serverless(createApp(loadConfig()));
