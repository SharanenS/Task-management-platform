import "server-only";
import { createClient } from "redis";
import type { Store } from "./policy";
function makeClient(url: string) {
  return createClient({
    url,
    socket: { connectTimeout: 3000, reconnectStrategy: false },
    disableOfflineQueue: true,
  });
}
type Client = ReturnType<typeof makeClient>;
let active: Client | undefined;
let pending: Promise<Client> | undefined;
function discard(client: Client) {
  if (active === client) {
    active = undefined;
    pending = undefined;
  }
  if (client.isOpen) client.destroy();
}
async function connection(): Promise<Client> {
  if (active && !active.isReady && !active.isOpen) discard(active);
  if (!pending) {
    const url = process.env.AUTH_REDIS_URL;
    if (!url) throw new Error("Session store is not configured");
    const client = makeClient(url);
    active = client;
    client.on("error", () => {
      console.error("Authentication dependency unavailable: session_store");
    });
    pending = client
      .connect()
      .then(() => client)
      .catch(() => {
        discard(client);
        throw new Error("Session store unavailable");
      });
  }
  const client = await pending;
  if (!client.isReady) {
    discard(client);
    throw new Error("Session store unavailable");
  }
  return client;
}
async function command<T>(action: (client: Client) => Promise<T>): Promise<T> {
  const client = await connection();
  try {
    return await action(client);
  } catch {
    discard(client);
    throw new Error("Session store unavailable");
  }
}
export const authStore: Store = {
  async put(key, value, ttl) {
    await command((client) =>
      client.set(key, value, { expiration: { type: "EX", value: ttl } }),
    );
  },
  async get(key) {
    return command((client) => client.get(key));
  },
  async take(key) {
    return command((client) => client.getDel(key));
  },
  async remove(key) {
    await command((client) => client.del(key));
  },
};
