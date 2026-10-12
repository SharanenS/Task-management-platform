import { getOperationAST, print } from "graphql";
import type { TypedDocumentNode } from "@graphql-typed-document-node/core";

export async function requestGraphQL<TResult, TVariables>(
  document: TypedDocumentNode<TResult, TVariables>,
  signal?: AbortSignal,
): Promise<TResult> {
  const timeout = AbortSignal.timeout(8_000);
  const response = await fetch("/graphql", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: print(document),
      operationName: getOperationAST(document)?.name?.value,
    }),
    cache: "no-store",
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
  });
  if (!response.ok) throw new Error("The gateway is unavailable.");
  const result: { data?: TResult; errors?: unknown[] } = await response.json();
  if (result.errors?.length || !result.data)
    throw new Error("The gateway returned an invalid response.");
  return result.data;
}
