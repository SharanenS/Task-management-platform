/** Internal type. DO NOT USE DIRECTLY. */
type Exact<T extends { [key: string]: unknown }> = { [K in keyof T]: T[K] };
/** Internal type. DO NOT USE DIRECTLY. */
export type Incremental<T> =
  | T
  | {
      [P in keyof T]?: P extends " $fragmentName" | "__typename" ? T[P] : never;
    };
import { TypedDocumentNode as DocumentNode } from "@graphql-typed-document-node/core";
export type CalendarConfigurationInput = {
  exceptions: Array<CalendarExceptionInput>;
  holidays: Array<CalendarHolidayInput>;
  timezone: string;
  week: Array<CalendarWeekdayInput>;
};

export type CalendarExceptionInput = {
  closes?: string | null | undefined;
  date: string;
  label: string;
  opens?: string | null | undefined;
  working: boolean;
};

export type CalendarHolidayInput = {
  date: string;
  label: string;
};

export type CalendarWeekdayInput = {
  closes?: string | null | undefined;
  opens?: string | null | undefined;
  weekday: number;
  working: boolean;
};

export type ChangeAccountInput = {
  accountId: string | number;
  action: string;
  requestId: string | number;
  role?: string | null | undefined;
  version: number;
};

export type ChangeProjectMembershipInput = {
  accountId: string | number;
  action: string;
  confirm: boolean;
  duties?: string;
  projectId: string | number;
  requestId: string | number;
  responsibility?: string;
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

export type CreateProjectInput = {
  confirm: boolean;
  previewId: string | number;
  requestId: string | number;
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

export type ProjectPreviewInput = {
  deadlineDate: string;
  name: string;
  objectives: string;
};

export type PublishCalendarInput = {
  confirm: boolean;
  previewId: string | number;
  requestId: string | number;
};

export type RecoverAccountInput = {
  operationId: string | number;
  requestId: string | number;
};

export type WorkingDaysInput = {
  duration: number;
  start: string;
  versionId: string | number;
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

export type CalendarConfigurationFieldsFragment = {
  timezone: string;
  week: Array<{
    weekday: number;
    working: boolean;
    opens: string | null;
    closes: string | null;
  }>;
  holidays: Array<{ date: string; label: string }>;
  exceptions: Array<{
    date: string;
    label: string;
    working: boolean;
    opens: string | null;
    closes: string | null;
  }>;
};

export type CompanyCalendarQueryVariables = Exact<{ [key: string]: never }>;

export type CompanyCalendarQuery = {
  companyCalendar: {
    current: {
      id: string;
      number: number;
      tzdbVersion: string;
      actorId: string;
      createdAt: string;
      config: {
        timezone: string;
        week: Array<{
          weekday: number;
          working: boolean;
          opens: string | null;
          closes: string | null;
        }>;
        holidays: Array<{ date: string; label: string }>;
        exceptions: Array<{
          date: string;
          label: string;
          working: boolean;
          opens: string | null;
          closes: string | null;
        }>;
      };
    } | null;
    history: Array<{
      id: string;
      number: number;
      tzdbVersion: string;
      actorId: string;
      createdAt: string;
    }>;
  };
};

export type PreviewCompanyCalendarMutationVariables = Exact<{
  input: CalendarConfigurationInput;
}>;

export type PreviewCompanyCalendarMutation = {
  previewCompanyCalendar: {
    previewId: string;
    baseNumber: number;
    tzdbVersion: string;
    expiresAt: string;
    changedSections: Array<string>;
    config: {
      timezone: string;
      week: Array<{
        weekday: number;
        working: boolean;
        opens: string | null;
        closes: string | null;
      }>;
      holidays: Array<{ date: string; label: string }>;
      exceptions: Array<{
        date: string;
        label: string;
        working: boolean;
        opens: string | null;
        closes: string | null;
      }>;
    };
  };
};

export type PublishCompanyCalendarMutationVariables = Exact<{
  input: PublishCalendarInput;
}>;

export type PublishCompanyCalendarMutation = {
  publishCompanyCalendar: {
    id: string;
    number: number;
    tzdbVersion: string;
    actorId: string;
    createdAt: string;
    config: {
      timezone: string;
      week: Array<{
        weekday: number;
        working: boolean;
        opens: string | null;
        closes: string | null;
      }>;
      holidays: Array<{ date: string; label: string }>;
      exceptions: Array<{
        date: string;
        label: string;
        working: boolean;
        opens: string | null;
        closes: string | null;
      }>;
    };
  };
};

export type CalculateWorkingDaysQueryVariables = Exact<{
  input: WorkingDaysInput;
}>;

export type CalculateWorkingDaysQuery = {
  calculateWorkingDays: {
    versionId: string;
    versionNumber: number;
    tzdbVersion: string;
    requestedStart: string;
    effectiveStart: string;
    adjusted: boolean;
    duration: number;
    countedDates: Array<string>;
    timezone: string;
    startsAt: string;
    dueAt: string;
    dueLocal: string;
    nextHandoff: string;
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

export type ProjectMembershipQueryVariables = Exact<{
  id: string | number;
}>;

export type ProjectMembershipQuery = {
  projectMembership: {
    canManage: boolean;
    responsibility: string;
    project: {
      id: string;
      name: string;
      objectives: string;
      ownerName: string;
      creatorName: string;
      deadlineLocal: string;
      timezone: string;
      version: number;
    };
    members: Array<{
      id: string;
      accountId: string | null;
      displayName: string;
      responsibility: string;
      duties: string | null;
      active: boolean;
    }>;
    history: Array<{
      id: string;
      actorId: string;
      targetId: string;
      action: string;
      before: string;
      after: string;
      projectVersion: number;
      createdAt: string;
    }>;
  };
};

export type ProjectCandidatesQueryVariables = Exact<{
  id: string | number;
  page: number;
  search: string;
}>;

export type ProjectCandidatesQuery = {
  projectCandidates: {
    hasMore: boolean;
    candidates: Array<{
      accountId: string;
      displayName: string;
      role: string;
      active: boolean;
    }>;
  };
};

export type ChangeProjectMembershipMutationVariables = Exact<{
  input: ChangeProjectMembershipInput;
}>;

export type ChangeProjectMembershipMutation = {
  changeProjectMembership: {
    projectId: string;
    version: number;
    changeId: string;
  };
};

export type ProjectFieldsFragment = {
  id: string;
  name: string;
  objectives: string;
  creatorId: string;
  creatorName: string;
  ownerId: string;
  ownerName: string;
  deadlineDate: string;
  approvedDeadline: string;
  deadlineLocal: string;
  calendarVersionId: string;
  calendarNumber: number;
  timezone: string;
  tzdbVersion: string;
  createdAt: string;
  version: number;
};

export type ProjectWorkspaceQueryVariables = Exact<{
  page: number;
  search: string;
}>;

export type ProjectWorkspaceQuery = {
  projectWorkspace: {
    hasMore: boolean;
    projects: Array<{
      id: string;
      name: string;
      objectives: string;
      creatorId: string;
      creatorName: string;
      ownerId: string;
      ownerName: string;
      deadlineDate: string;
      approvedDeadline: string;
      deadlineLocal: string;
      calendarVersionId: string;
      calendarNumber: number;
      timezone: string;
      tzdbVersion: string;
      createdAt: string;
      version: number;
    }>;
    calendar: {
      id: string;
      number: number;
      timezone: string;
      tzdbVersion: string;
    } | null;
  };
};

export type ProjectDetailQueryVariables = Exact<{
  id: string | number;
}>;

export type ProjectDetailQuery = {
  project: {
    id: string;
    name: string;
    objectives: string;
    creatorId: string;
    creatorName: string;
    ownerId: string;
    ownerName: string;
    deadlineDate: string;
    approvedDeadline: string;
    deadlineLocal: string;
    calendarVersionId: string;
    calendarNumber: number;
    timezone: string;
    tzdbVersion: string;
    createdAt: string;
    version: number;
  };
};

export type PreviewProjectMutationVariables = Exact<{
  input: ProjectPreviewInput;
}>;

export type PreviewProjectMutation = {
  previewProject: {
    previewId: string;
    name: string;
    objectives: string;
    deadlineDate: string;
    approvedDeadline: string;
    deadlineLocal: string;
    calendarNumber: number;
    timezone: string;
    tzdbVersion: string;
    expiresAt: string;
    pastDeadline: boolean;
  };
};

export type CreateProjectMutationVariables = Exact<{
  input: CreateProjectInput;
}>;

export type CreateProjectMutation = {
  createProject: {
    id: string;
    name: string;
    objectives: string;
    creatorId: string;
    creatorName: string;
    ownerId: string;
    ownerName: string;
    deadlineDate: string;
    approvedDeadline: string;
    deadlineLocal: string;
    calendarVersionId: string;
    calendarNumber: number;
    timezone: string;
    tzdbVersion: string;
    createdAt: string;
    version: number;
  };
};

export const CalendarConfigurationFieldsFragmentDoc = {
  kind: "Document",
  definitions: [
    {
      kind: "FragmentDefinition",
      name: { kind: "Name", value: "CalendarConfigurationFields" },
      typeCondition: {
        kind: "NamedType",
        name: { kind: "Name", value: "CalendarConfiguration" },
      },
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          { kind: "Field", name: { kind: "Name", value: "timezone" } },
          {
            kind: "Field",
            name: { kind: "Name", value: "week" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "weekday" } },
                { kind: "Field", name: { kind: "Name", value: "working" } },
                { kind: "Field", name: { kind: "Name", value: "opens" } },
                { kind: "Field", name: { kind: "Name", value: "closes" } },
              ],
            },
          },
          {
            kind: "Field",
            name: { kind: "Name", value: "holidays" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "date" } },
                { kind: "Field", name: { kind: "Name", value: "label" } },
              ],
            },
          },
          {
            kind: "Field",
            name: { kind: "Name", value: "exceptions" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "date" } },
                { kind: "Field", name: { kind: "Name", value: "label" } },
                { kind: "Field", name: { kind: "Name", value: "working" } },
                { kind: "Field", name: { kind: "Name", value: "opens" } },
                { kind: "Field", name: { kind: "Name", value: "closes" } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<CalendarConfigurationFieldsFragment, unknown>;
export const ProjectFieldsFragmentDoc = {
  kind: "Document",
  definitions: [
    {
      kind: "FragmentDefinition",
      name: { kind: "Name", value: "ProjectFields" },
      typeCondition: {
        kind: "NamedType",
        name: { kind: "Name", value: "ProjectRecord" },
      },
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          { kind: "Field", name: { kind: "Name", value: "id" } },
          { kind: "Field", name: { kind: "Name", value: "name" } },
          { kind: "Field", name: { kind: "Name", value: "objectives" } },
          { kind: "Field", name: { kind: "Name", value: "creatorId" } },
          { kind: "Field", name: { kind: "Name", value: "creatorName" } },
          { kind: "Field", name: { kind: "Name", value: "ownerId" } },
          { kind: "Field", name: { kind: "Name", value: "ownerName" } },
          { kind: "Field", name: { kind: "Name", value: "deadlineDate" } },
          { kind: "Field", name: { kind: "Name", value: "approvedDeadline" } },
          { kind: "Field", name: { kind: "Name", value: "deadlineLocal" } },
          { kind: "Field", name: { kind: "Name", value: "calendarVersionId" } },
          { kind: "Field", name: { kind: "Name", value: "calendarNumber" } },
          { kind: "Field", name: { kind: "Name", value: "timezone" } },
          { kind: "Field", name: { kind: "Name", value: "tzdbVersion" } },
          { kind: "Field", name: { kind: "Name", value: "createdAt" } },
          { kind: "Field", name: { kind: "Name", value: "version" } },
        ],
      },
    },
  ],
} as unknown as DocumentNode<ProjectFieldsFragment, unknown>;
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
export const CompanyCalendarDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "query",
      name: { kind: "Name", value: "CompanyCalendar" },
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "companyCalendar" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                {
                  kind: "Field",
                  name: { kind: "Name", value: "current" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      { kind: "Field", name: { kind: "Name", value: "id" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "number" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "tzdbVersion" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "actorId" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "createdAt" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "config" },
                        selectionSet: {
                          kind: "SelectionSet",
                          selections: [
                            {
                              kind: "FragmentSpread",
                              name: {
                                kind: "Name",
                                value: "CalendarConfigurationFields",
                              },
                            },
                          ],
                        },
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
                        name: { kind: "Name", value: "number" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "tzdbVersion" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "actorId" },
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
    {
      kind: "FragmentDefinition",
      name: { kind: "Name", value: "CalendarConfigurationFields" },
      typeCondition: {
        kind: "NamedType",
        name: { kind: "Name", value: "CalendarConfiguration" },
      },
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          { kind: "Field", name: { kind: "Name", value: "timezone" } },
          {
            kind: "Field",
            name: { kind: "Name", value: "week" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "weekday" } },
                { kind: "Field", name: { kind: "Name", value: "working" } },
                { kind: "Field", name: { kind: "Name", value: "opens" } },
                { kind: "Field", name: { kind: "Name", value: "closes" } },
              ],
            },
          },
          {
            kind: "Field",
            name: { kind: "Name", value: "holidays" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "date" } },
                { kind: "Field", name: { kind: "Name", value: "label" } },
              ],
            },
          },
          {
            kind: "Field",
            name: { kind: "Name", value: "exceptions" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "date" } },
                { kind: "Field", name: { kind: "Name", value: "label" } },
                { kind: "Field", name: { kind: "Name", value: "working" } },
                { kind: "Field", name: { kind: "Name", value: "opens" } },
                { kind: "Field", name: { kind: "Name", value: "closes" } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  CompanyCalendarQuery,
  CompanyCalendarQueryVariables
>;
export const PreviewCompanyCalendarDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "mutation",
      name: { kind: "Name", value: "PreviewCompanyCalendar" },
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
              name: { kind: "Name", value: "CalendarConfigurationInput" },
            },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "previewCompanyCalendar" },
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
                { kind: "Field", name: { kind: "Name", value: "previewId" } },
                { kind: "Field", name: { kind: "Name", value: "baseNumber" } },
                { kind: "Field", name: { kind: "Name", value: "tzdbVersion" } },
                { kind: "Field", name: { kind: "Name", value: "expiresAt" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "changedSections" },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "config" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      {
                        kind: "FragmentSpread",
                        name: {
                          kind: "Name",
                          value: "CalendarConfigurationFields",
                        },
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
    {
      kind: "FragmentDefinition",
      name: { kind: "Name", value: "CalendarConfigurationFields" },
      typeCondition: {
        kind: "NamedType",
        name: { kind: "Name", value: "CalendarConfiguration" },
      },
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          { kind: "Field", name: { kind: "Name", value: "timezone" } },
          {
            kind: "Field",
            name: { kind: "Name", value: "week" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "weekday" } },
                { kind: "Field", name: { kind: "Name", value: "working" } },
                { kind: "Field", name: { kind: "Name", value: "opens" } },
                { kind: "Field", name: { kind: "Name", value: "closes" } },
              ],
            },
          },
          {
            kind: "Field",
            name: { kind: "Name", value: "holidays" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "date" } },
                { kind: "Field", name: { kind: "Name", value: "label" } },
              ],
            },
          },
          {
            kind: "Field",
            name: { kind: "Name", value: "exceptions" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "date" } },
                { kind: "Field", name: { kind: "Name", value: "label" } },
                { kind: "Field", name: { kind: "Name", value: "working" } },
                { kind: "Field", name: { kind: "Name", value: "opens" } },
                { kind: "Field", name: { kind: "Name", value: "closes" } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  PreviewCompanyCalendarMutation,
  PreviewCompanyCalendarMutationVariables
>;
export const PublishCompanyCalendarDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "mutation",
      name: { kind: "Name", value: "PublishCompanyCalendar" },
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
              name: { kind: "Name", value: "PublishCalendarInput" },
            },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "publishCompanyCalendar" },
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
                { kind: "Field", name: { kind: "Name", value: "id" } },
                { kind: "Field", name: { kind: "Name", value: "number" } },
                { kind: "Field", name: { kind: "Name", value: "tzdbVersion" } },
                { kind: "Field", name: { kind: "Name", value: "actorId" } },
                { kind: "Field", name: { kind: "Name", value: "createdAt" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "config" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      {
                        kind: "FragmentSpread",
                        name: {
                          kind: "Name",
                          value: "CalendarConfigurationFields",
                        },
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
    {
      kind: "FragmentDefinition",
      name: { kind: "Name", value: "CalendarConfigurationFields" },
      typeCondition: {
        kind: "NamedType",
        name: { kind: "Name", value: "CalendarConfiguration" },
      },
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          { kind: "Field", name: { kind: "Name", value: "timezone" } },
          {
            kind: "Field",
            name: { kind: "Name", value: "week" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "weekday" } },
                { kind: "Field", name: { kind: "Name", value: "working" } },
                { kind: "Field", name: { kind: "Name", value: "opens" } },
                { kind: "Field", name: { kind: "Name", value: "closes" } },
              ],
            },
          },
          {
            kind: "Field",
            name: { kind: "Name", value: "holidays" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "date" } },
                { kind: "Field", name: { kind: "Name", value: "label" } },
              ],
            },
          },
          {
            kind: "Field",
            name: { kind: "Name", value: "exceptions" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "date" } },
                { kind: "Field", name: { kind: "Name", value: "label" } },
                { kind: "Field", name: { kind: "Name", value: "working" } },
                { kind: "Field", name: { kind: "Name", value: "opens" } },
                { kind: "Field", name: { kind: "Name", value: "closes" } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  PublishCompanyCalendarMutation,
  PublishCompanyCalendarMutationVariables
>;
export const CalculateWorkingDaysDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "query",
      name: { kind: "Name", value: "CalculateWorkingDays" },
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
              name: { kind: "Name", value: "WorkingDaysInput" },
            },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "calculateWorkingDays" },
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
                { kind: "Field", name: { kind: "Name", value: "versionId" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "versionNumber" },
                },
                { kind: "Field", name: { kind: "Name", value: "tzdbVersion" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "requestedStart" },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "effectiveStart" },
                },
                { kind: "Field", name: { kind: "Name", value: "adjusted" } },
                { kind: "Field", name: { kind: "Name", value: "duration" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "countedDates" },
                },
                { kind: "Field", name: { kind: "Name", value: "timezone" } },
                { kind: "Field", name: { kind: "Name", value: "startsAt" } },
                { kind: "Field", name: { kind: "Name", value: "dueAt" } },
                { kind: "Field", name: { kind: "Name", value: "dueLocal" } },
                { kind: "Field", name: { kind: "Name", value: "nextHandoff" } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  CalculateWorkingDaysQuery,
  CalculateWorkingDaysQueryVariables
>;
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
export const ProjectMembershipDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "query",
      name: { kind: "Name", value: "ProjectMembership" },
      variableDefinitions: [
        {
          kind: "VariableDefinition",
          variable: { kind: "Variable", name: { kind: "Name", value: "id" } },
          type: {
            kind: "NonNullType",
            type: { kind: "NamedType", name: { kind: "Name", value: "ID" } },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "projectMembership" },
            arguments: [
              {
                kind: "Argument",
                name: { kind: "Name", value: "id" },
                value: {
                  kind: "Variable",
                  name: { kind: "Name", value: "id" },
                },
              },
            ],
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                {
                  kind: "Field",
                  name: { kind: "Name", value: "project" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      { kind: "Field", name: { kind: "Name", value: "id" } },
                      { kind: "Field", name: { kind: "Name", value: "name" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "objectives" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "ownerName" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "creatorName" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "deadlineLocal" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "timezone" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "version" },
                      },
                    ],
                  },
                },
                { kind: "Field", name: { kind: "Name", value: "canManage" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "responsibility" },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "members" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      { kind: "Field", name: { kind: "Name", value: "id" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "accountId" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "displayName" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "responsibility" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "duties" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "active" },
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
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "before" },
                      },
                      { kind: "Field", name: { kind: "Name", value: "after" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "projectVersion" },
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
  ProjectMembershipQuery,
  ProjectMembershipQueryVariables
>;
export const ProjectCandidatesDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "query",
      name: { kind: "Name", value: "ProjectCandidates" },
      variableDefinitions: [
        {
          kind: "VariableDefinition",
          variable: { kind: "Variable", name: { kind: "Name", value: "id" } },
          type: {
            kind: "NonNullType",
            type: { kind: "NamedType", name: { kind: "Name", value: "ID" } },
          },
        },
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
            name: { kind: "Name", value: "projectCandidates" },
            arguments: [
              {
                kind: "Argument",
                name: { kind: "Name", value: "id" },
                value: {
                  kind: "Variable",
                  name: { kind: "Name", value: "id" },
                },
              },
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
                  name: { kind: "Name", value: "candidates" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "accountId" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "displayName" },
                      },
                      { kind: "Field", name: { kind: "Name", value: "role" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "active" },
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
  ProjectCandidatesQuery,
  ProjectCandidatesQueryVariables
>;
export const ChangeProjectMembershipDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "mutation",
      name: { kind: "Name", value: "ChangeProjectMembership" },
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
              name: { kind: "Name", value: "ChangeProjectMembershipInput" },
            },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "changeProjectMembership" },
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
                { kind: "Field", name: { kind: "Name", value: "projectId" } },
                { kind: "Field", name: { kind: "Name", value: "version" } },
                { kind: "Field", name: { kind: "Name", value: "changeId" } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  ChangeProjectMembershipMutation,
  ChangeProjectMembershipMutationVariables
>;
export const ProjectWorkspaceDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "query",
      name: { kind: "Name", value: "ProjectWorkspace" },
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
            name: { kind: "Name", value: "projectWorkspace" },
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
                  name: { kind: "Name", value: "projects" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      {
                        kind: "FragmentSpread",
                        name: { kind: "Name", value: "ProjectFields" },
                      },
                    ],
                  },
                },
                { kind: "Field", name: { kind: "Name", value: "hasMore" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "calendar" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      { kind: "Field", name: { kind: "Name", value: "id" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "number" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "timezone" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "tzdbVersion" },
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
    {
      kind: "FragmentDefinition",
      name: { kind: "Name", value: "ProjectFields" },
      typeCondition: {
        kind: "NamedType",
        name: { kind: "Name", value: "ProjectRecord" },
      },
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          { kind: "Field", name: { kind: "Name", value: "id" } },
          { kind: "Field", name: { kind: "Name", value: "name" } },
          { kind: "Field", name: { kind: "Name", value: "objectives" } },
          { kind: "Field", name: { kind: "Name", value: "creatorId" } },
          { kind: "Field", name: { kind: "Name", value: "creatorName" } },
          { kind: "Field", name: { kind: "Name", value: "ownerId" } },
          { kind: "Field", name: { kind: "Name", value: "ownerName" } },
          { kind: "Field", name: { kind: "Name", value: "deadlineDate" } },
          { kind: "Field", name: { kind: "Name", value: "approvedDeadline" } },
          { kind: "Field", name: { kind: "Name", value: "deadlineLocal" } },
          { kind: "Field", name: { kind: "Name", value: "calendarVersionId" } },
          { kind: "Field", name: { kind: "Name", value: "calendarNumber" } },
          { kind: "Field", name: { kind: "Name", value: "timezone" } },
          { kind: "Field", name: { kind: "Name", value: "tzdbVersion" } },
          { kind: "Field", name: { kind: "Name", value: "createdAt" } },
          { kind: "Field", name: { kind: "Name", value: "version" } },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  ProjectWorkspaceQuery,
  ProjectWorkspaceQueryVariables
>;
export const ProjectDetailDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "query",
      name: { kind: "Name", value: "ProjectDetail" },
      variableDefinitions: [
        {
          kind: "VariableDefinition",
          variable: { kind: "Variable", name: { kind: "Name", value: "id" } },
          type: {
            kind: "NonNullType",
            type: { kind: "NamedType", name: { kind: "Name", value: "ID" } },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "project" },
            arguments: [
              {
                kind: "Argument",
                name: { kind: "Name", value: "id" },
                value: {
                  kind: "Variable",
                  name: { kind: "Name", value: "id" },
                },
              },
            ],
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                {
                  kind: "FragmentSpread",
                  name: { kind: "Name", value: "ProjectFields" },
                },
              ],
            },
          },
        ],
      },
    },
    {
      kind: "FragmentDefinition",
      name: { kind: "Name", value: "ProjectFields" },
      typeCondition: {
        kind: "NamedType",
        name: { kind: "Name", value: "ProjectRecord" },
      },
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          { kind: "Field", name: { kind: "Name", value: "id" } },
          { kind: "Field", name: { kind: "Name", value: "name" } },
          { kind: "Field", name: { kind: "Name", value: "objectives" } },
          { kind: "Field", name: { kind: "Name", value: "creatorId" } },
          { kind: "Field", name: { kind: "Name", value: "creatorName" } },
          { kind: "Field", name: { kind: "Name", value: "ownerId" } },
          { kind: "Field", name: { kind: "Name", value: "ownerName" } },
          { kind: "Field", name: { kind: "Name", value: "deadlineDate" } },
          { kind: "Field", name: { kind: "Name", value: "approvedDeadline" } },
          { kind: "Field", name: { kind: "Name", value: "deadlineLocal" } },
          { kind: "Field", name: { kind: "Name", value: "calendarVersionId" } },
          { kind: "Field", name: { kind: "Name", value: "calendarNumber" } },
          { kind: "Field", name: { kind: "Name", value: "timezone" } },
          { kind: "Field", name: { kind: "Name", value: "tzdbVersion" } },
          { kind: "Field", name: { kind: "Name", value: "createdAt" } },
          { kind: "Field", name: { kind: "Name", value: "version" } },
        ],
      },
    },
  ],
} as unknown as DocumentNode<ProjectDetailQuery, ProjectDetailQueryVariables>;
export const PreviewProjectDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "mutation",
      name: { kind: "Name", value: "PreviewProject" },
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
              name: { kind: "Name", value: "ProjectPreviewInput" },
            },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "previewProject" },
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
                { kind: "Field", name: { kind: "Name", value: "previewId" } },
                { kind: "Field", name: { kind: "Name", value: "name" } },
                { kind: "Field", name: { kind: "Name", value: "objectives" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "deadlineDate" },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "approvedDeadline" },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "deadlineLocal" },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "calendarNumber" },
                },
                { kind: "Field", name: { kind: "Name", value: "timezone" } },
                { kind: "Field", name: { kind: "Name", value: "tzdbVersion" } },
                { kind: "Field", name: { kind: "Name", value: "expiresAt" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "pastDeadline" },
                },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  PreviewProjectMutation,
  PreviewProjectMutationVariables
>;
export const CreateProjectDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "mutation",
      name: { kind: "Name", value: "CreateProject" },
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
              name: { kind: "Name", value: "CreateProjectInput" },
            },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "createProject" },
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
                {
                  kind: "FragmentSpread",
                  name: { kind: "Name", value: "ProjectFields" },
                },
              ],
            },
          },
        ],
      },
    },
    {
      kind: "FragmentDefinition",
      name: { kind: "Name", value: "ProjectFields" },
      typeCondition: {
        kind: "NamedType",
        name: { kind: "Name", value: "ProjectRecord" },
      },
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          { kind: "Field", name: { kind: "Name", value: "id" } },
          { kind: "Field", name: { kind: "Name", value: "name" } },
          { kind: "Field", name: { kind: "Name", value: "objectives" } },
          { kind: "Field", name: { kind: "Name", value: "creatorId" } },
          { kind: "Field", name: { kind: "Name", value: "creatorName" } },
          { kind: "Field", name: { kind: "Name", value: "ownerId" } },
          { kind: "Field", name: { kind: "Name", value: "ownerName" } },
          { kind: "Field", name: { kind: "Name", value: "deadlineDate" } },
          { kind: "Field", name: { kind: "Name", value: "approvedDeadline" } },
          { kind: "Field", name: { kind: "Name", value: "deadlineLocal" } },
          { kind: "Field", name: { kind: "Name", value: "calendarVersionId" } },
          { kind: "Field", name: { kind: "Name", value: "calendarNumber" } },
          { kind: "Field", name: { kind: "Name", value: "timezone" } },
          { kind: "Field", name: { kind: "Name", value: "tzdbVersion" } },
          { kind: "Field", name: { kind: "Name", value: "createdAt" } },
          { kind: "Field", name: { kind: "Name", value: "version" } },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  CreateProjectMutation,
  CreateProjectMutationVariables
>;
