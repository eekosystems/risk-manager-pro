type LogLevel = "debug" | "info" | "warn" | "error";

const LOG_LEVEL_PRIORITY: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

const currentLevel: LogLevel =
  (import.meta.env.VITE_LOG_LEVEL as LogLevel) ?? "warn";

function shouldLog(level: LogLevel): boolean {
  return LOG_LEVEL_PRIORITY[level] >= LOG_LEVEL_PRIORITY[currentLevel];
}

export const logger = {
  debug(message: string, ...args: unknown[]): void {
    if (shouldLog("debug")) console.debug(`[RMP] ${message}`, ...args);
  },
  info(message: string, ...args: unknown[]): void {
    if (shouldLog("info")) console.info(`[RMP] ${message}`, ...args);
  },
  warn(message: string, ...args: unknown[]): void {
    if (shouldLog("warn")) console.warn(`[RMP] ${message}`, ...args);
  },
  error(message: string, ...args: unknown[]): void {
    if (shouldLog("error")) console.error(`[RMP] ${message}`, ...args);
  },
};
