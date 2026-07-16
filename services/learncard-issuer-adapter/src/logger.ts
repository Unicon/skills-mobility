// Minimal leveled logger gated by LOG_LEVEL (default "info") — mirrors the
// Python services' logging.basicConfig + LOG_LEVEL convention without a dep.
const LEVELS = ["error", "warn", "info", "debug"] as const;
type Level = (typeof LEVELS)[number];

const configured = (process.env.LOG_LEVEL ?? "info").toLowerCase();
const threshold = LEVELS.includes(configured as Level) ? (configured as Level) : "info";
const enabled = (level: Level): boolean => LEVELS.indexOf(level) <= LEVELS.indexOf(threshold);

function emit(level: Level, msg: string, fields: Record<string, unknown> = {}): void {
  if (!enabled(level)) return;
  const parts = Object.entries(fields).map(([k, v]) => `${k}=${v}`);
  // eslint-disable-next-line no-console
  console[level === "debug" ? "log" : level](`${level.toUpperCase()} ${msg}`, ...parts);
}

export const logger = {
  error: (msg: string, fields?: Record<string, unknown>) => emit("error", msg, fields),
  warn: (msg: string, fields?: Record<string, unknown>) => emit("warn", msg, fields),
  info: (msg: string, fields?: Record<string, unknown>) => emit("info", msg, fields),
  debug: (msg: string, fields?: Record<string, unknown>) => emit("debug", msg, fields),
};
