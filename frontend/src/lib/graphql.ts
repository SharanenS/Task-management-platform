import { getOperationAST, print } from "graphql";
import type { TypedDocumentNode } from "@graphql-typed-document-node/core";

export async function requestGraphQL<TResult, TVariables>(
  document: TypedDocumentNode<TResult, TVariables>,
  variables?: TVariables,
  signal?: AbortSignal,
): Promise<TResult> {
  const timeout = AbortSignal.timeout(8_000);
  const response = await fetch("/graphql", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: print(document),
      operationName: getOperationAST(document)?.name?.value,
      variables,
    }),
    cache: "no-store",
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
  });
  if (!response.ok) throw new Error("The gateway is unavailable.");
  const result: {
    data?: TResult;
    errors?: Array<{ message?: string; extensions?: { code?: string } }>;
  } = await response.json();
  if (result.errors?.length || !result.data) {
    const first = result.errors?.[0];
    throw new GraphQLRequestError(
      first?.message ?? "The request could not be completed.",
      first?.extensions?.code,
    );
  }
  return result.data;
}

export class GraphQLRequestError extends Error {
  constructor(
    message: string,
    public readonly code?: string,
  ) {
    super(message);
    this.name = "GraphQLRequestError";
  }
}
