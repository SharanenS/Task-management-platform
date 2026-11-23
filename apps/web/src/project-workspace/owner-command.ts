export async function sendOwnerCommand<T>(
  command: string,
  input: unknown,
): Promise<T> {
  const response = await fetch("/projects/owner-command", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command, input }),
  });
  const value = await response.json();
  if (!response.ok)
    throw new Error(
      value.error ?? "Owner request unavailable. Refresh to check its outcome.",
    );
  return value as T;
}
