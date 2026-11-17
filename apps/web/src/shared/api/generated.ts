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
  employeeId?: string | number | null | undefined;
  requestId: string | number;
  role: string;
  username: string;
};

export type OrganizationChangeInput = {
  accountId?: string | number | null | undefined;
  action: string;
  active?: boolean | null | undefined;
  departmentId?: string | number | null | undefined;
  entityId?: string | number | null | undefined;
  jobTitleId?: string | number | null | undefined;
  kind?: string | null | undefined;
  managerId?: string | number | null | undefined;
  name?: string | null | undefined;
  requestId: string | number;
  version?: number | null | undefined;
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

export type OrganizationWorkspaceQueryVariables = Exact<{
  page: number;
  search: string;
}>;

export type OrganizationWorkspaceQuery = {
  organizationWorkspace: {
    hasMore: boolean;
    departments: Array<{
      id: string;
      name: string;
      active: boolean;
      version: number;
    }>;
    jobTitles: Array<{
      id: string;
      name: string;
      active: boolean;
      version: number;
    }>;
    employees: Array<{
      id: string;
      displayName: string;
      active: boolean;
      version: number;
      accountId: string | null;
      companyRole: string;
      departmentId: string | null;
      jobTitleId: string | null;
      managerId: string | null;
    }>;
    managerOptions: Array<{ id: string; displayName: string }>;
    unlinkedEmployees: Array<{ id: string; displayName: string }>;
    availableAccounts: Array<{ id: string; companyRole: string }>;
    history: Array<{
      id: string;
      action: string;
      entityKind: string;
      entityName: string;
      actorName: string;
      createdAt: string;
    }>;
  };
};

export type ChangeOrganizationMutationVariables = Exact<{
  input: OrganizationChangeInput;
}>;

export type ChangeOrganizationMutation = {
  changeOrganization: { entityId: string; state: string };
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
export const OrganizationWorkspaceDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "query",
      name: { kind: "Name", value: "OrganizationWorkspace" },
      variableDefinitions: [
        {
          kind: "VariableDefinition",
          variable: { kind: "Variable", name: { kind: "Name", value: "page" } },
          type: {
            kind: "NonNullType",
            type: { kind: "NamedType", name: { kind: "Name", value: "Int" } },
          },
        },
        {
          kind: "VariableDefinition",
          variable: {
            kind: "Variable",
            name: { kind: "Name", value: "search" },
          },
          type: {
            kind: "NonNullType",
            type: {
              kind: "NamedType",
              name: { kind: "Name", value: "String" },
            },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "organizationWorkspace" },
            arguments: [
              {
                kind: "Argument",
                name: { kind: "Name", value: "page" },
                value: {
                  kind: "Variable",
                  name: { kind: "Name", value: "page" },
                },
              },
              {
                kind: "Argument",
                name: { kind: "Name", value: "search" },
                value: {
                  kind: "Variable",
                  name: { kind: "Name", value: "search" },
                },
              },
            ],
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                {
                  kind: "Field",
                  name: { kind: "Name", value: "departments" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      { kind: "Field", name: { kind: "Name", value: "id" } },
                      { kind: "Field", name: { kind: "Name", value: "name" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "active" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "version" },
                      },
                    ],
                  },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "jobTitles" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      { kind: "Field", name: { kind: "Name", value: "id" } },
                      { kind: "Field", name: { kind: "Name", value: "name" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "active" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "version" },
                      },
                    ],
                  },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "employees" },
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
                        name: { kind: "Name", value: "active" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "version" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "accountId" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "companyRole" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "departmentId" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "jobTitleId" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "managerId" },
                      },
                    ],
                  },
                },
                { kind: "Field", name: { kind: "Name", value: "hasMore" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "managerOptions" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      { kind: "Field", name: { kind: "Name", value: "id" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "displayName" },
                      },
                    ],
                  },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "unlinkedEmployees" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      { kind: "Field", name: { kind: "Name", value: "id" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "displayName" },
                      },
                    ],
                  },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "availableAccounts" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      { kind: "Field", name: { kind: "Name", value: "id" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "companyRole" },
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
                        name: { kind: "Name", value: "action" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "entityKind" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "entityName" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "actorName" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "createdAt" },
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
} as unknown as DocumentNode<
  OrganizationWorkspaceQuery,
  OrganizationWorkspaceQueryVariables
>;
export const ChangeOrganizationDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "mutation",
      name: { kind: "Name", value: "ChangeOrganization" },
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
              name: { kind: "Name", value: "OrganizationChangeInput" },
            },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "changeOrganization" },
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
                { kind: "Field", name: { kind: "Name", value: "entityId" } },
                { kind: "Field", name: { kind: "Name", value: "state" } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  ChangeOrganizationMutation,
  ChangeOrganizationMutationVariables
>;
