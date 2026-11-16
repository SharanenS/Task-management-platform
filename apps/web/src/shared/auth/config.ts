import "server-only";

export function authConfig() {
  const app = new URL(process.env.AUTH_APP_URL ?? "http://127.0.0.1:3020");
  const issuer = new URL(
    process.env.AUTH_ISSUER ?? "http://127.0.0.1:8180/realms/taskspace-portals",
  );
  for (const url of [app, issuer]) {
    if (url.username || url.password || url.search || url.hash)
      throw new Error("Invalid authentication configuration");
    if (
      url.protocol !== "https:" &&
      !(
        process.env.AUTH_ALLOW_LOCAL_HTTP === "true" &&
        url.protocol === "http:" &&
        ["127.0.0.1", "localhost"].includes(url.hostname)
      )
    ) {
      throw new Error(
        "Authentication requires HTTPS or explicit loopback development mode",
      );
    }
  }
  if (app.pathname !== "/" || issuer.pathname !== "/realms/taskspace-portals")
    throw new Error("Invalid authentication boundary");
  const internal = new URL(process.env.AUTH_INTERNAL_ISSUER ?? issuer.href);
  if (
    internal.pathname !== issuer.pathname ||
    internal.search ||
    internal.hash ||
    internal.username ||
    internal.password ||
    (internal.origin !== issuer.origin &&
      !(
        process.env.AUTH_ALLOW_LOCAL_HTTP === "true" &&
        internal.origin === "http://identity:8080"
      ))
  ) {
    throw new Error("Invalid internal authentication boundary");
  }
  const secure = app.protocol === "https:";
  return {
    origin: app.origin,
    issuer: issuer.href.replace(/\/$/, ""),
    internalIssuer: internal.href.replace(/\/$/, ""),
    clientId: "taskspace-portals-web",
    callback: `${app.origin}/auth/callback`,
    secure,
    sessionCookie: secure ? "__Host-taskspace_session" : "taskspace_session",
    transactionCookie: secure
      ? "__Host-taskspace_transaction"
      : "taskspace_transaction",
  };
}
