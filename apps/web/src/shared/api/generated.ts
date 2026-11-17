/** Internal type. DO NOT USE DIRECTLY. */
type Exact<T extends { [key: string]: unknown }> = { [K in keyof T]: T[K] };
/** Internal type. DO NOT USE DIRECTLY. */
export type Incremental<T> =
  | T
  | {
      [P in keyof T]?: P extends " $fragmentName" | "__typename" ? T[P] : never;
    };
import { TypedDocumentNode as DocumentNode } from "@graphql-typed-document-node/core";
export type ChangeAccountInput = {
  accountId: string | number;
  action: string;
  requestId: string | number;
  role?: string | null | undefined;
  version: number;
};

export type CreateAccountInput = {
  displayName: string;
  email: string;
  requestId: string | number;
  role: string;
  username: string;
};

export type RecoverAccountInput = {
  operationId: string | number;
  requestId: string | number;
};

export type AccountAdministrationQueryVariables = Exact<{
  page: number;
}>;

export type AccountAdministrationQuery = {
  accountAdministration: {
    hasMore: boolean;
    accounts: Array<{
      id: string;
      displayName: string;
      username: string;
      email: string;
      active: boolean;
      profileActive: boolean;
      role: string;
      version: number;
    }>;
    operations: Array<{
      id: string;
      username: string;
      email: string;
      state: string;
      failureCode: string | null;
    }>;
    history: Array<{
      id: string;
      actorId: string;
      targetId: string | null;
      action: string;
      state: string;
      before: string;
      after: string;
      createdAt: string;
    }>;
  };
};

export type CreateAccountMutationVariables = Exact<{
  input: CreateAccountInput;
}>;

export type CreateAccountMutation = {
  createAccount: { operationId: string; state: string };
};

export type ChangeAccountMutationVariables = Exact<{
  input: ChangeAccountInput;
}>;

export type ChangeAccountMutation = {
  changeAccount: { operationId: string; state: string };
};

export type RecoverAccountMutationVariables = Exact<{
  input: RecoverAccountInput;
}>;

export type RecoverAccountMutation = {
  recoverAccount: { operationId: string; state: string };
};

export type AccountEntryQueryVariables = Exact<{ [key: string]: never }>;

export type AccountEntryQuery = {
  viewer: {
    accountId: string;
    employeeId: string;
    displayName: string;
    companyRoles: Array<string>;
    permissions: Array<string>;
  };
};

export type AdminWorkspaceQueryVariables = Exact<{ [key: string]: never }>;

export type AdminWorkspaceQuery = {
  adminWorkspace: {
    viewer: {
      accountId: string;
      employeeId: string;
      displayName: string;
      companyRoles: Array<string>;
      permissions: Array<string>;
    };
  };
};

export const AccountAdministrationDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "query",
      name: { kind: "Name", value: "AccountAdministration" },
      variableDefinitions: [
        {
          kind: "VariableDefinition",
          variable: { kind: "Variable", name: { kind: "Name", value: "page" } },
          type: {
            kind: "NonNullType",
            type: { kind: "NamedType", name: { kind: "Name", value: "Int" } },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "accountAdministration" },
            arguments: [
              {
                kind: "Argument",
                name: { kind: "Name", value: "page" },
                value: {
                  kind: "Variable",
                  name: { kind: "Name", value: "page" },
                },
              },
            ],
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                {
                  kind: "Field",
                  name: { kind: "Name", value: "accounts" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      { kind: "Field", name: { kind: "Name", value: "id" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "displayName" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "username" },
                      },
                      { kind: "Field", name: { kind: "Name", value: "email" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "active" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "profileActive" },
                      },
                      { kind: "Field", name: { kind: "Name", value: "role" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "version" },
                      },
                    ],
                  },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "operations" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      { kind: "Field", name: { kind: "Name", value: "id" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "username" },
                      },
                      { kind: "Field", name: { kind: "Name", value: "email" } },
                      { kind: "Field", name: { kind: "Name", value: "state" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "failureCode" },
                      },
                    ],
                  },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "history" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      { kind: "Field", name: { kind: "Name", value: "id" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "actorId" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "targetId" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "action" },
                      },
                      { kind: "Field", name: { kind: "Name", value: "state" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "before" },
                      },
                      { kind: "Field", name: { kind: "Name", value: "after" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "createdAt" },
                      },
                    ],
                  },
                },
                { kind: "Field", name: { kind: "Name", value: "hasMore" } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  AccountAdministrationQuery,
  AccountAdministrationQueryVariables
>;
export const CreateAccountDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "mutation",
      name: { kind: "Name", value: "CreateAccount" },
      variableDefinitions: [
        {
          kind: "VariableDefinition",
          variable: {
            kind: "Variable",
            name: { kind: "Name", value: "input" },
          },
          type: {
            kind: "NonNullType",
            type: {
              kind: "NamedType",
              name: { kind: "Name", value: "CreateAccountInput" },
            },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "createAccount" },
            arguments: [
              {
                kind: "Argument",
                name: { kind: "Name", value: "input" },
                value: {
                  kind: "Variable",
                  name: { kind: "Name", value: "input" },
                },
              },
            ],
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "operationId" } },
                { kind: "Field", name: { kind: "Name", value: "state" } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  CreateAccountMutation,
  CreateAccountMutationVariables
>;
export const ChangeAccountDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "mutation",
      name: { kind: "Name", value: "ChangeAccount" },
      variableDefinitions: [
        {
          kind: "VariableDefinition",
          variable: {
            kind: "Variable",
            name: { kind: "Name", value: "input" },
          },
          type: {
            kind: "NonNullType",
            type: {
              kind: "NamedType",
              name: { kind: "Name", value: "ChangeAccountInput" },
            },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "changeAccount" },
            arguments: [
              {
                kind: "Argument",
                name: { kind: "Name", value: "input" },
                value: {
                  kind: "Variable",
                  name: { kind: "Name", value: "input" },
                },
              },
            ],
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "operationId" } },
                { kind: "Field", name: { kind: "Name", value: "state" } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  ChangeAccountMutation,
  ChangeAccountMutationVariables
>;
export const RecoverAccountDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "mutation",
      name: { kind: "Name", value: "RecoverAccount" },
      variableDefinitions: [
        {
          kind: "VariableDefinition",
          variable: {
            kind: "Variable",
            name: { kind: "Name", value: "input" },
          },
          type: {
            kind: "NonNullType",
            type: {
              kind: "NamedType",
              name: { kind: "Name", value: "RecoverAccountInput" },
            },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "recoverAccount" },
            arguments: [
              {
                kind: "Argument",
                name: { kind: "Name", value: "input" },
                value: {
                  kind: "Variable",
                  name: { kind: "Name", value: "input" },
                },
              },
            ],
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "operationId" } },
                { kind: "Field", name: { kind: "Name", value: "state" } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  RecoverAccountMutation,
  RecoverAccountMutationVariables
>;
export const AccountEntryDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "query",
      name: { kind: "Name", value: "AccountEntry" },
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "viewer" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "accountId" } },
                { kind: "Field", name: { kind: "Name", value: "employeeId" } },
                { kind: "Field", name: { kind: "Name", value: "displayName" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "companyRoles" },
                },
                { kind: "Field", name: { kind: "Name", value: "permissions" } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<AccountEntryQuery, AccountEntryQueryVariables>;
export const AdminWorkspaceDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "query",
      name: { kind: "Name", value: "AdminWorkspace" },
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "adminWorkspace" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                {
                  kind: "Field",
                  name: { kind: "Name", value: "viewer" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "accountId" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "employeeId" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "displayName" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "companyRoles" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "permissions" },
                      },
                    ],
                  },
                },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<AdminWorkspaceQuery, AdminWorkspaceQueryVariables>;
