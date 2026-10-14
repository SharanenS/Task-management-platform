import { createClient, type RedisClientType } from "redis";

const globalRedis = globalThis as typeof globalThis & {
  taskspaceRedis?: RedisClientType;
  taskspaceRedisPromise?: Promise<RedisClientType>;
};

export async function getRedis(): Promise<RedisClientType> {
  if (globalRedis.taskspaceRedis?.isReady) return globalRedis.taskspaceRedis;
  if (!globalRedis.taskspaceRedisPromise) {
    const client = createClient({
      url: process.env.REDIS_URL ?? "redis://127.0.0.1:6380",
    });
    client.on("error", () => undefined);
    globalRedis.taskspaceRedisPromise = client.connect().then(() => {
      globalRedis.taskspaceRedis = client;
      return client;
    });
  }
  return globalRedis.taskspaceRedisPromise;
}
