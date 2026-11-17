/** Internal type. DO NOT USE DIRECTLY. */
type Exact<T extends { [key: string]: unknown }> = { [K in keyof T]: T[K] };
/** Internal type. DO NOT USE DIRECTLY. */
export type Incremental<T> =
  | T
  | {
      [P in keyof T]?: P extends " $fragmentName" | "__typename" ? T[P] : never;
    };
import { TypedDocumentNode as DocumentNode } from "@graphql-typed-document-node/core";
export type Maybe<T> = T | null;
export type InputMaybe<T> = Maybe<T>;
/** All built-in and custom scalars, mapped to their actual values */
export type Scalars = {
  ID: { input: string; output: string };
  String: { input: string; output: string };
  Boolean: { input: boolean; output: boolean };
  Int: { input: number; output: number };
  Float: { input: number; output: number };
};

export type AdminWorkspace = {
  __typename?: "AdminWorkspace";
  viewer: Viewer;
};

export type Query = {
  __typename?: "Query";
  adminWorkspace: AdminWorkspace;
  viewer: Viewer;
};

export type Viewer = {
  __typename?: "Viewer";
  accountId: Scalars["ID"]["output"];
  companyRoles: Array<Scalars["String"]["output"]>;
  displayName: Scalars["String"]["output"];
  employeeId: Scalars["ID"]["output"];
  permissions: Array<Scalars["String"]["output"]>;
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
