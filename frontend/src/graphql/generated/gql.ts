/* eslint-disable */
import * as types from './graphql';
import type { TypedDocumentNode as DocumentNode } from '@graphql-typed-document-node/core';

/**
 * Map of all GraphQL operations in the project.
 *
 * This map has several performance disadvantages:
 * 1. It is not tree-shakeable, so it will include all operations in the project.
 * 2. It is not minifiable, so the string of a GraphQL query will be multiple times inside the bundle.
 * 3. It does not support dead code elimination, so it will add unused operations.
 *
 * Therefore it is highly recommended to use the babel or swc plugin for production.
 * Learn more about it here: https://the-guild.dev/graphql/codegen/plugins/presets/preset-client#reducing-bundle-size
 */
type Documents = {
    "query EmployeeDirectory($first: Int!, $after: String, $search: String, $role: ApplicationRole, $active: Boolean) {\n  employees(\n    first: $first\n    after: $after\n    search: $search\n    role: $role\n    active: $active\n  ) {\n    nodes {\n      id\n      username\n      displayName\n      email\n      role\n      active\n      provisioningStatus\n      updatedAt\n    }\n    pageInfo {\n      hasNextPage\n      endCursor\n    }\n  }\n}\n\nquery EmployeeDetail($id: ID!) {\n  employee(id: $id) {\n    id\n    username\n    displayName\n    email\n    role\n    active\n    provisioningStatus\n    createdAt\n    updatedAt\n    version\n  }\n}\n\nmutation ProvisionEmployee($input: ProvisionEmployeeInput!) {\n  provisionEmployee(input: $input) {\n    id\n    username\n    displayName\n    email\n    role\n    active\n    provisioningStatus\n  }\n}\n\nmutation UpdateEmployeeRole($employeeId: ID!, $role: ApplicationRole!) {\n  updateEmployeeRole(employeeId: $employeeId, role: $role) {\n    id\n    role\n    active\n    provisioningStatus\n    version\n  }\n}\n\nmutation SetEmployeeActive($employeeId: ID!, $active: Boolean!) {\n  setEmployeeActive(employeeId: $employeeId, active: $active) {\n    id\n    role\n    active\n    provisioningStatus\n    version\n  }\n}\n\nmutation ReconcileEmployee($employeeId: ID!) {\n  reconcileEmployee(employeeId: $employeeId) {\n    id\n    active\n    provisioningStatus\n    version\n  }\n}": typeof types.EmployeeDirectoryDocument,
    "query SystemInfo {\n  systemInfo {\n    name\n    version\n    environment\n    status\n  }\n}": typeof types.SystemInfoDocument,
};
const documents: Documents = {
    "query EmployeeDirectory($first: Int!, $after: String, $search: String, $role: ApplicationRole, $active: Boolean) {\n  employees(\n    first: $first\n    after: $after\n    search: $search\n    role: $role\n    active: $active\n  ) {\n    nodes {\n      id\n      username\n      displayName\n      email\n      role\n      active\n      provisioningStatus\n      updatedAt\n    }\n    pageInfo {\n      hasNextPage\n      endCursor\n    }\n  }\n}\n\nquery EmployeeDetail($id: ID!) {\n  employee(id: $id) {\n    id\n    username\n    displayName\n    email\n    role\n    active\n    provisioningStatus\n    createdAt\n    updatedAt\n    version\n  }\n}\n\nmutation ProvisionEmployee($input: ProvisionEmployeeInput!) {\n  provisionEmployee(input: $input) {\n    id\n    username\n    displayName\n    email\n    role\n    active\n    provisioningStatus\n  }\n}\n\nmutation UpdateEmployeeRole($employeeId: ID!, $role: ApplicationRole!) {\n  updateEmployeeRole(employeeId: $employeeId, role: $role) {\n    id\n    role\n    active\n    provisioningStatus\n    version\n  }\n}\n\nmutation SetEmployeeActive($employeeId: ID!, $active: Boolean!) {\n  setEmployeeActive(employeeId: $employeeId, active: $active) {\n    id\n    role\n    active\n    provisioningStatus\n    version\n  }\n}\n\nmutation ReconcileEmployee($employeeId: ID!) {\n  reconcileEmployee(employeeId: $employeeId) {\n    id\n    active\n    provisioningStatus\n    version\n  }\n}": types.EmployeeDirectoryDocument,
    "query SystemInfo {\n  systemInfo {\n    name\n    version\n    environment\n    status\n  }\n}": types.SystemInfoDocument,
};

/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 *
 *
 * @example
 * ```ts
 * const query = graphql(`query GetUser($id: ID!) { user(id: $id) { name } }`);
 * ```
 *
 * The query argument is unknown!
 * Please regenerate the types.
 */
export function graphql(source: string): unknown;

/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(source: "query EmployeeDirectory($first: Int!, $after: String, $search: String, $role: ApplicationRole, $active: Boolean) {\n  employees(\n    first: $first\n    after: $after\n    search: $search\n    role: $role\n    active: $active\n  ) {\n    nodes {\n      id\n      username\n      displayName\n      email\n      role\n      active\n      provisioningStatus\n      updatedAt\n    }\n    pageInfo {\n      hasNextPage\n      endCursor\n    }\n  }\n}\n\nquery EmployeeDetail($id: ID!) {\n  employee(id: $id) {\n    id\n    username\n    displayName\n    email\n    role\n    active\n    provisioningStatus\n    createdAt\n    updatedAt\n    version\n  }\n}\n\nmutation ProvisionEmployee($input: ProvisionEmployeeInput!) {\n  provisionEmployee(input: $input) {\n    id\n    username\n    displayName\n    email\n    role\n    active\n    provisioningStatus\n  }\n}\n\nmutation UpdateEmployeeRole($employeeId: ID!, $role: ApplicationRole!) {\n  updateEmployeeRole(employeeId: $employeeId, role: $role) {\n    id\n    role\n    active\n    provisioningStatus\n    version\n  }\n}\n\nmutation SetEmployeeActive($employeeId: ID!, $active: Boolean!) {\n  setEmployeeActive(employeeId: $employeeId, active: $active) {\n    id\n    role\n    active\n    provisioningStatus\n    version\n  }\n}\n\nmutation ReconcileEmployee($employeeId: ID!) {\n  reconcileEmployee(employeeId: $employeeId) {\n    id\n    active\n    provisioningStatus\n    version\n  }\n}"): (typeof documents)["query EmployeeDirectory($first: Int!, $after: String, $search: String, $role: ApplicationRole, $active: Boolean) {\n  employees(\n    first: $first\n    after: $after\n    search: $search\n    role: $role\n    active: $active\n  ) {\n    nodes {\n      id\n      username\n      displayName\n      email\n      role\n      active\n      provisioningStatus\n      updatedAt\n    }\n    pageInfo {\n      hasNextPage\n      endCursor\n    }\n  }\n}\n\nquery EmployeeDetail($id: ID!) {\n  employee(id: $id) {\n    id\n    username\n    displayName\n    email\n    role\n    active\n    provisioningStatus\n    createdAt\n    updatedAt\n    version\n  }\n}\n\nmutation ProvisionEmployee($input: ProvisionEmployeeInput!) {\n  provisionEmployee(input: $input) {\n    id\n    username\n    displayName\n    email\n    role\n    active\n    provisioningStatus\n  }\n}\n\nmutation UpdateEmployeeRole($employeeId: ID!, $role: ApplicationRole!) {\n  updateEmployeeRole(employeeId: $employeeId, role: $role) {\n    id\n    role\n    active\n    provisioningStatus\n    version\n  }\n}\n\nmutation SetEmployeeActive($employeeId: ID!, $active: Boolean!) {\n  setEmployeeActive(employeeId: $employeeId, active: $active) {\n    id\n    role\n    active\n    provisioningStatus\n    version\n  }\n}\n\nmutation ReconcileEmployee($employeeId: ID!) {\n  reconcileEmployee(employeeId: $employeeId) {\n    id\n    active\n    provisioningStatus\n    version\n  }\n}"];
/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(source: "query SystemInfo {\n  systemInfo {\n    name\n    version\n    environment\n    status\n  }\n}"): (typeof documents)["query SystemInfo {\n  systemInfo {\n    name\n    version\n    environment\n    status\n  }\n}"];

export function graphql(source: string) {
  return (documents as any)[source] ?? {};
}

export type DocumentType<TDocumentNode extends DocumentNode<any, any>> = TDocumentNode extends DocumentNode<  infer TType,  any>  ? TType  : never;