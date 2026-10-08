import { Pool } from "pg";

declare global {
  // eslint-disable-next-line no-var
  var __dashboardPgPool: Pool | undefined;
}

function createPool(): Pool {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error("DATABASE_URL is not set");
  }
  return new Pool({ connectionString, ssl: { rejectUnauthorized: false } });
}

/** Singleton pool reused across requests/hot-reloads in the Next.js server runtime. */
export function getPool(): Pool {
  if (!global.__dashboardPgPool) {
    global.__dashboardPgPool = createPool();
  }
  return global.__dashboardPgPool;
}
