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

export type ChangeTaskInput = {
  acceptanceCriteria?: string | null | undefined;
  action: string;
  assigneeId?: string | number | null | undefined;
  confirm: boolean;
  instructions?: string | null | undefined;
  projectId: string | number;
  projectVersion: number;
  reason: string;
  requestId: string | number;
  taskId?: string | number | null | undefined;
  title?: string | null | undefined;
  version: number;
};

export type CommitTaskScheduleInput = {
  confirm: boolean;
  previewId: string | number;
  projectId: string | number;
  requestId: string | number;
};

export type CreateAccountInput = {
  displayName: string;
  email: string;
  employeeId?: string | number | null | undefined;
  requestId: string | number;
  role: string;
  username: string;
};

export type CreateCoordinationInput = {
  acknowledgementRequired: boolean;
  confirm: boolean;
  details: string;
  dueAt: string;
  kind: string;
  location: string;
  projectId: string | number;
  recipients: Array<string | number>;
  requestId: string | number;
  topic: string;
};

export type CreateProjectInput = {
  confirm: boolean;
  previewId: string | number;
  requestId: string | number;
};

export type ExecuteTaskInput = {
  action: string;
  blocker?: string | null | undefined;
  confirm: boolean;
  note: string;
  progress: number;
  projectId: string | number;
  projectVersion: number;
  requestId: string | number;
  taskId: string | number;
  version: number;
};

export type FollowUpCoordinationInput = {
  confirm: boolean;
  nextFollowUpAt: string;
  note: string;
  projectId: string | number;
  recordId: string | number;
  requestId: string | number;
  version: number;
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

export type PreviewOwnerDeadlineInput = {
  deadlineDate: string;
  escalationId: string | number;
  projectId: string | number;
  version: number;
};

export type PreviewTaskScheduleInput = {
  duration: number;
  prerequisites: Array<string | number>;
  projectId: string | number;
  projectVersion: number;
  reason: string;
  requestedStart: string;
  taskId: string | number;
  version: number;
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

export type RecordOwnerDecisionInput = {
  affectedTeam: string;
  confirm: boolean;
  escalationId: string | number;
  outcome: string;
  previewId?: string | number | null | undefined;
  projectId: string | number;
  projectVersion: number;
  reason: string;
  requestId: string | number;
  version: number;
};

export type RecordReviewFallbackInput = {
  confirm: boolean;
  endsAt: string;
  leaderId?: string | number | null | undefined;
  projectId: string | number;
  projectVersion: number;
  reason: string;
  requestId: string | number;
  scope: string;
  startsAt: string;
};

export type RecoverAccountInput = {
  operationId: string | number;
  requestId: string | number;
};

export type ReviewCompletionInput = {
  confirm: boolean;
  feedback: string;
  outcome: string;
  projectId: string | number;
  projectVersion: number;
  requestId: string | number;
  selfConfirm: boolean;
  submissionId: string | number;
  taskId: string | number;
  version: number;
};

export type RevokeReviewFallbackInput = {
  confirm: boolean;
  projectId: string | number;
  reason: string;
  recordId: string | number;
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

export type ProjectReviewsQueryVariables = Exact<{
  id: string | number;
  page: number;
}>;

export type ProjectReviewsQuery = {
  projectReviews: {
    isLeader: boolean;
    canReview: boolean;
    fallbackId: string | null;
    hasMore: boolean;
    project: { id: string; name: string; version: number; timezone: string };
    tasks: Array<{
      id: string;
      title: string;
      status: string;
      version: number;
      own: boolean;
      canAct: boolean;
      canReview: boolean;
      assigneeName: string | null;
      instructions: string;
      acceptanceCriteria: string;
      progress: number;
      blocker: string | null;
      startedAt: string | null;
      completedAt: string | null;
      workHistory: Array<{
        id: string;
        action: string;
        note: string;
        actorName: string;
        createdAt: string;
        progress: number;
        blocker: string | null;
        status: string;
      }>;
      submissions: Array<{
        id: string;
        submitterName: string;
        submittedAt: string;
        version: number;
        summary: string;
        snapshot: string;
        pending: boolean;
        decision: {
          actorName: string;
          outcome: string;
          feedback: string;
          selfApproval: boolean;
          fallbackId: string | null;
          decidedAt: string;
        } | null;
      }>;
    }>;
  };
};

export type ExecuteTaskMutationVariables = Exact<{
  input: ExecuteTaskInput;
}>;

export type ExecuteTaskMutation = {
  executeTask: { taskId: string; version: number; projectVersion: number };
};

export type ReviewCompletionMutationVariables = Exact<{
  input: ReviewCompletionInput;
}>;

export type ReviewCompletionMutation = {
  reviewCompletion: { taskId: string; version: number; projectVersion: number };
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

export type OwnerOversightQueryVariables = Exact<{
  id: string | number;
  page: number;
}>;

export type OwnerOversightQuery = {
  ownerOversight: {
    currentDeadline: string;
    originalOverdue: boolean;
    currentOverdue: boolean;
    forecastAt: string | null;
    forecastState: string;
    forecastLate: boolean | null;
    actualDeliveryAt: string | null;
    hasMore: boolean;
    project: {
      id: string;
      name: string;
      version: number;
      approvedDeadline: string;
      deadlineLocal: string;
      timezone: string;
      ownerName: string;
    };
    escalations: Array<{
      id: string;
      sourceRequestId: string;
      version: number;
      reason: string;
      affectedTeam: string;
      assessmentState: string;
      forecastAt: string | null;
      assessmentSummary: string | null;
      createdAt: string;
    }>;
    history: Array<{
      id: string;
      escalationId: string;
      outcome: string;
      actorId: string;
      actorName: string;
      actorRole: string;
      reason: string;
      affectedTeam: string;
      forecastAt: string | null;
      assessmentState: string;
      previousDeadline: string;
      revisedDeadline: string | null;
      previousOverdue: boolean;
      projectVersion: number;
      createdAt: string;
    }>;
  };
};

export type ReviewFallbacksQueryVariables = Exact<{
  id: string | number;
  page: number;
}>;

export type ReviewFallbacksQuery = {
  reviewFallbacks: {
    canRecord: boolean;
    leaderId: string | null;
    leaderName: string | null;
    hasMore: boolean;
    records: Array<{
      id: string;
      leaderId: string | null;
      leaderName: string | null;
      scope: string;
      reason: string;
      actorId: string;
      actorName: string;
      startsAt: string;
      endsAt: string;
      createdAt: string;
      active: boolean;
      revokedAt: string | null;
      revokedBy: string | null;
      revocationReason: string | null;
    }>;
  };
};

export type PreviewOwnerDeadlineMutationVariables = Exact<{
  input: PreviewOwnerDeadlineInput;
}>;

export type PreviewOwnerDeadlineMutation = {
  previewOwnerDeadline: {
    id: string;
    deadlineAt: string;
    deadlineLocal: string;
    originalDeadline: string;
    currentDeadline: string;
    forecastAt: string;
    calendarNumber: number;
    expiresAt: string;
  };
};

export type RecordOwnerDecisionMutationVariables = Exact<{
  input: RecordOwnerDecisionInput;
}>;

export type RecordOwnerDecisionMutation = {
  recordOwnerDecision: { id: string; outcome: string };
};

export type RecordReviewFallbackMutationVariables = Exact<{
  input: RecordReviewFallbackInput;
}>;

export type RecordReviewFallbackMutation = {
  recordReviewFallback: { id: string; active: boolean };
};

export type RevokeReviewFallbackMutationVariables = Exact<{
  input: RevokeReviewFallbackInput;
}>;

export type RevokeReviewFallbackMutation = {
  revokeReviewFallback: { id: string; active: boolean };
};

export type CoordinationFieldsFragment = {
  id: string;
  projectId: string;
  kind: string;
  topic: string;
  details: string;
  dueAt: string;
  location: string;
  acknowledgementRequired: boolean;
  version: number;
  createdAt: string;
  overdue: boolean;
  recipients: Array<{
    accountId: string;
    displayName: string;
    acknowledgement: string;
    responseState: string;
  }>;
  followUps: Array<{
    id: string;
    actorId: string;
    note: string;
    nextFollowUpAt: string;
    createdAt: string;
  }>;
};

export type ProjectCoordinationQueryVariables = Exact<{
  id: string | number;
  page: number;
}>;

export type ProjectCoordinationQuery = {
  projectCoordination: {
    hasMore: boolean;
    records: Array<{
      id: string;
      projectId: string;
      kind: string;
      topic: string;
      details: string;
      dueAt: string;
      location: string;
      acknowledgementRequired: boolean;
      version: number;
      createdAt: string;
      overdue: boolean;
      recipients: Array<{
        accountId: string;
        displayName: string;
        acknowledgement: string;
        responseState: string;
      }>;
      followUps: Array<{
        id: string;
        actorId: string;
        note: string;
        nextFollowUpAt: string;
        createdAt: string;
      }>;
    }>;
  };
};

export type CreateCoordinationMutationVariables = Exact<{
  input: CreateCoordinationInput;
}>;

export type CreateCoordinationMutation = {
  createCoordination: {
    id: string;
    projectId: string;
    kind: string;
    topic: string;
    details: string;
    dueAt: string;
    location: string;
    acknowledgementRequired: boolean;
    version: number;
    createdAt: string;
    overdue: boolean;
    recipients: Array<{
      accountId: string;
      displayName: string;
      acknowledgement: string;
      responseState: string;
    }>;
    followUps: Array<{
      id: string;
      actorId: string;
      note: string;
      nextFollowUpAt: string;
      createdAt: string;
    }>;
  };
};

export type FollowUpCoordinationMutationVariables = Exact<{
  input: FollowUpCoordinationInput;
}>;

export type FollowUpCoordinationMutation = {
  followUpCoordination: {
    id: string;
    projectId: string;
    kind: string;
    topic: string;
    details: string;
    dueAt: string;
    location: string;
    acknowledgementRequired: boolean;
    version: number;
    createdAt: string;
    overdue: boolean;
    recipients: Array<{
      accountId: string;
      displayName: string;
      acknowledgement: string;
      responseState: string;
    }>;
    followUps: Array<{
      id: string;
      actorId: string;
      note: string;
      nextFollowUpAt: string;
      createdAt: string;
    }>;
  };
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

export type ProjectTasksQueryVariables = Exact<{
  id: string | number;
  page: number;
}>;

export type ProjectTasksQuery = {
  projectTasks: {
    canPlan: boolean;
    hasMore: boolean;
    project: { id: string; name: string; version: number };
    tasks: Array<{
      id: string;
      title: string;
      status: string;
      assigneeName: string | null;
      details: {
        instructions: string;
        acceptanceCriteria: string;
        version: number;
        assigneeId: string | null;
        assignedAt: string | null;
        history: Array<{
          id: string;
          action: string;
          reason: string;
          actorName: string;
          before: string;
          after: string;
          version: number;
          createdAt: string;
        }>;
      } | null;
    }>;
  };
};

export type TaskCandidatesQueryVariables = Exact<{
  id: string | number;
  page: number;
}>;

export type TaskCandidatesQuery = {
  taskCandidates: {
    hasMore: boolean;
    candidates: Array<{ accountId: string; displayName: string }>;
  };
};

export type ChangeTaskMutationVariables = Exact<{
  input: ChangeTaskInput;
}>;

export type ChangeTaskMutation = {
  changeTask: { taskId: string; version: number; projectVersion: number };
};

export type SchedulePointFieldsFragment = {
  id: string;
  requestedStart: string | null;
  duration: number | null;
  prerequisites: Array<string>;
  effectiveStart: string | null;
  startsAt: string | null;
  dueAt: string | null;
  nextHandoff: string | null;
  adjusted: boolean;
  readiness: string;
  issue: string | null;
};

export type ScheduleAnalysisFieldsFragment = {
  state: string;
  forecastAt: string | null;
  capacityChecked: boolean;
  tasks: Array<{
    id: string;
    requestedStart: string | null;
    duration: number | null;
    prerequisites: Array<string>;
    effectiveStart: string | null;
    startsAt: string | null;
    dueAt: string | null;
    nextHandoff: string | null;
    adjusted: boolean;
    readiness: string;
    issue: string | null;
  }>;
  overlaps: Array<{ taskId: string; otherTaskId: string }>;
};

export type ProjectScheduleQueryVariables = Exact<{
  id: string | number;
}>;

export type ProjectScheduleQuery = {
  projectSchedule: {
    canPlan: boolean;
    state: string | null;
    forecastAt: string | null;
    timezone: string;
    calendarNumber: number;
    currentDeadline: string;
    project: {
      id: string;
      name: string;
      version: number;
      approvedDeadline: string;
    };
    tasks: Array<{
      title: string;
      version: number;
      status: string;
      assigneeName: string | null;
      plan: {
        id: string;
        requestedStart: string | null;
        duration: number | null;
        prerequisites: Array<string>;
        effectiveStart: string | null;
        startsAt: string | null;
        dueAt: string | null;
        nextHandoff: string | null;
        adjusted: boolean;
        readiness: string;
        issue: string | null;
      };
      original: {
        id: string;
        requestedStart: string | null;
        duration: number | null;
        prerequisites: Array<string>;
        effectiveStart: string | null;
        startsAt: string | null;
        dueAt: string | null;
        nextHandoff: string | null;
        adjusted: boolean;
        readiness: string;
        issue: string | null;
      } | null;
    }>;
    overlaps: Array<{ taskId: string; otherTaskId: string }>;
    history: Array<{
      id: string;
      actorName: string;
      reason: string;
      createdAt: string;
      before: {
        state: string;
        forecastAt: string | null;
        capacityChecked: boolean;
        tasks: Array<{
          id: string;
          requestedStart: string | null;
          duration: number | null;
          prerequisites: Array<string>;
          effectiveStart: string | null;
          startsAt: string | null;
          dueAt: string | null;
          nextHandoff: string | null;
          adjusted: boolean;
          readiness: string;
          issue: string | null;
        }>;
        overlaps: Array<{ taskId: string; otherTaskId: string }>;
      };
      after: {
        state: string;
        forecastAt: string | null;
        capacityChecked: boolean;
        tasks: Array<{
          id: string;
          requestedStart: string | null;
          duration: number | null;
          prerequisites: Array<string>;
          effectiveStart: string | null;
          startsAt: string | null;
          dueAt: string | null;
          nextHandoff: string | null;
          adjusted: boolean;
          readiness: string;
          issue: string | null;
        }>;
        overlaps: Array<{ taskId: string; otherTaskId: string }>;
      };
    }>;
  };
};

export type PreviewTaskScheduleMutationVariables = Exact<{
  input: PreviewTaskScheduleInput;
}>;

export type PreviewTaskScheduleMutation = {
  previewTaskSchedule: {
    previewId: string;
    validUntil: string;
    calendarNumber: number;
    timezone: string;
    approvedDeadline: string;
    exceedsDeadline: boolean;
    before: {
      state: string;
      forecastAt: string | null;
      capacityChecked: boolean;
      tasks: Array<{
        id: string;
        requestedStart: string | null;
        duration: number | null;
        prerequisites: Array<string>;
        effectiveStart: string | null;
        startsAt: string | null;
        dueAt: string | null;
        nextHandoff: string | null;
        adjusted: boolean;
        readiness: string;
        issue: string | null;
      }>;
      overlaps: Array<{ taskId: string; otherTaskId: string }>;
    };
    after: {
      state: string;
      forecastAt: string | null;
      capacityChecked: boolean;
      tasks: Array<{
        id: string;
        requestedStart: string | null;
        duration: number | null;
        prerequisites: Array<string>;
        effectiveStart: string | null;
        startsAt: string | null;
        dueAt: string | null;
        nextHandoff: string | null;
        adjusted: boolean;
        readiness: string;
        issue: string | null;
      }>;
      overlaps: Array<{ taskId: string; otherTaskId: string }>;
    };
  };
};

export type CommitTaskScheduleMutationVariables = Exact<{
  input: CommitTaskScheduleInput;
}>;

export type CommitTaskScheduleMutation = {
  commitTaskSchedule: { projectVersion: number; scheduleVersion: number };
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
export const CoordinationFieldsFragmentDoc = {
  kind: "Document",
  definitions: [
    {
      kind: "FragmentDefinition",
      name: { kind: "Name", value: "CoordinationFields" },
      typeCondition: {
        kind: "NamedType",
        name: { kind: "Name", value: "CoordinationRecord" },
      },
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          { kind: "Field", name: { kind: "Name", value: "id" } },
          { kind: "Field", name: { kind: "Name", value: "projectId" } },
          { kind: "Field", name: { kind: "Name", value: "kind" } },
          { kind: "Field", name: { kind: "Name", value: "topic" } },
          { kind: "Field", name: { kind: "Name", value: "details" } },
          { kind: "Field", name: { kind: "Name", value: "dueAt" } },
          { kind: "Field", name: { kind: "Name", value: "location" } },
          {
            kind: "Field",
            name: { kind: "Name", value: "acknowledgementRequired" },
          },
          { kind: "Field", name: { kind: "Name", value: "version" } },
          { kind: "Field", name: { kind: "Name", value: "createdAt" } },
          { kind: "Field", name: { kind: "Name", value: "overdue" } },
          {
            kind: "Field",
            name: { kind: "Name", value: "recipients" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "accountId" } },
                { kind: "Field", name: { kind: "Name", value: "displayName" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "acknowledgement" },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "responseState" },
                },
              ],
            },
          },
          {
            kind: "Field",
            name: { kind: "Name", value: "followUps" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "id" } },
                { kind: "Field", name: { kind: "Name", value: "actorId" } },
                { kind: "Field", name: { kind: "Name", value: "note" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "nextFollowUpAt" },
                },
                { kind: "Field", name: { kind: "Name", value: "createdAt" } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<CoordinationFieldsFragment, unknown>;
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
export const SchedulePointFieldsFragmentDoc = {
  kind: "Document",
  definitions: [
    {
      kind: "FragmentDefinition",
      name: { kind: "Name", value: "SchedulePointFields" },
      typeCondition: {
        kind: "NamedType",
        name: { kind: "Name", value: "SchedulePoint" },
      },
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          { kind: "Field", name: { kind: "Name", value: "id" } },
          { kind: "Field", name: { kind: "Name", value: "requestedStart" } },
          { kind: "Field", name: { kind: "Name", value: "duration" } },
          { kind: "Field", name: { kind: "Name", value: "prerequisites" } },
          { kind: "Field", name: { kind: "Name", value: "effectiveStart" } },
          { kind: "Field", name: { kind: "Name", value: "startsAt" } },
          { kind: "Field", name: { kind: "Name", value: "dueAt" } },
          { kind: "Field", name: { kind: "Name", value: "nextHandoff" } },
          { kind: "Field", name: { kind: "Name", value: "adjusted" } },
          { kind: "Field", name: { kind: "Name", value: "readiness" } },
          { kind: "Field", name: { kind: "Name", value: "issue" } },
        ],
      },
    },
  ],
} as unknown as DocumentNode<SchedulePointFieldsFragment, unknown>;
export const ScheduleAnalysisFieldsFragmentDoc = {
  kind: "Document",
  definitions: [
    {
      kind: "FragmentDefinition",
      name: { kind: "Name", value: "ScheduleAnalysisFields" },
      typeCondition: {
        kind: "NamedType",
        name: { kind: "Name", value: "ScheduleAnalysis" },
      },
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          { kind: "Field", name: { kind: "Name", value: "state" } },
          { kind: "Field", name: { kind: "Name", value: "forecastAt" } },
          { kind: "Field", name: { kind: "Name", value: "capacityChecked" } },
          {
            kind: "Field",
            name: { kind: "Name", value: "tasks" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                {
                  kind: "FragmentSpread",
                  name: { kind: "Name", value: "SchedulePointFields" },
                },
              ],
            },
          },
          {
            kind: "Field",
            name: { kind: "Name", value: "overlaps" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "taskId" } },
                { kind: "Field", name: { kind: "Name", value: "otherTaskId" } },
              ],
            },
          },
        ],
      },
    },
    {
      kind: "FragmentDefinition",
      name: { kind: "Name", value: "SchedulePointFields" },
      typeCondition: {
        kind: "NamedType",
        name: { kind: "Name", value: "SchedulePoint" },
      },
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          { kind: "Field", name: { kind: "Name", value: "id" } },
          { kind: "Field", name: { kind: "Name", value: "requestedStart" } },
          { kind: "Field", name: { kind: "Name", value: "duration" } },
          { kind: "Field", name: { kind: "Name", value: "prerequisites" } },
          { kind: "Field", name: { kind: "Name", value: "effectiveStart" } },
          { kind: "Field", name: { kind: "Name", value: "startsAt" } },
          { kind: "Field", name: { kind: "Name", value: "dueAt" } },
          { kind: "Field", name: { kind: "Name", value: "nextHandoff" } },
          { kind: "Field", name: { kind: "Name", value: "adjusted" } },
          { kind: "Field", name: { kind: "Name", value: "readiness" } },
          { kind: "Field", name: { kind: "Name", value: "issue" } },
        ],
      },
    },
  ],
} as unknown as DocumentNode<ScheduleAnalysisFieldsFragment, unknown>;
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
export const ProjectReviewsDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "query",
      name: { kind: "Name", value: "ProjectReviews" },
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
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "projectReviews" },
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
                        name: { kind: "Name", value: "version" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "timezone" },
                      },
                    ],
                  },
                },
                { kind: "Field", name: { kind: "Name", value: "isLeader" } },
                { kind: "Field", name: { kind: "Name", value: "canReview" } },
                { kind: "Field", name: { kind: "Name", value: "fallbackId" } },
                { kind: "Field", name: { kind: "Name", value: "hasMore" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "tasks" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      { kind: "Field", name: { kind: "Name", value: "id" } },
                      { kind: "Field", name: { kind: "Name", value: "title" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "status" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "version" },
                      },
                      { kind: "Field", name: { kind: "Name", value: "own" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "canAct" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "canReview" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "assigneeName" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "instructions" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "acceptanceCriteria" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "progress" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "blocker" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "startedAt" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "completedAt" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "workHistory" },
                        selectionSet: {
                          kind: "SelectionSet",
                          selections: [
                            {
                              kind: "Field",
                              name: { kind: "Name", value: "id" },
                            },
                            {
                              kind: "Field",
                              name: { kind: "Name", value: "action" },
                            },
                            {
                              kind: "Field",
                              name: { kind: "Name", value: "note" },
                            },
                            {
                              kind: "Field",
                              name: { kind: "Name", value: "actorName" },
                            },
                            {
                              kind: "Field",
                              name: { kind: "Name", value: "createdAt" },
                            },
                            {
                              kind: "Field",
                              name: { kind: "Name", value: "progress" },
                            },
                            {
                              kind: "Field",
                              name: { kind: "Name", value: "blocker" },
                            },
                            {
                              kind: "Field",
                              name: { kind: "Name", value: "status" },
                            },
                          ],
                        },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "submissions" },
                        selectionSet: {
                          kind: "SelectionSet",
                          selections: [
                            {
                              kind: "Field",
                              name: { kind: "Name", value: "id" },
                            },
                            {
                              kind: "Field",
                              name: { kind: "Name", value: "submitterName" },
                            },
                            {
                              kind: "Field",
                              name: { kind: "Name", value: "submittedAt" },
                            },
                            {
                              kind: "Field",
                              name: { kind: "Name", value: "version" },
                            },
                            {
                              kind: "Field",
                              name: { kind: "Name", value: "summary" },
                            },
                            {
                              kind: "Field",
                              name: { kind: "Name", value: "snapshot" },
                            },
                            {
                              kind: "Field",
                              name: { kind: "Name", value: "pending" },
                            },
                            {
                              kind: "Field",
                              name: { kind: "Name", value: "decision" },
                              selectionSet: {
                                kind: "SelectionSet",
                                selections: [
                                  {
                                    kind: "Field",
                                    name: { kind: "Name", value: "actorName" },
                                  },
                                  {
                                    kind: "Field",
                                    name: { kind: "Name", value: "outcome" },
                                  },
                                  {
                                    kind: "Field",
                                    name: { kind: "Name", value: "feedback" },
                                  },
                                  {
                                    kind: "Field",
                                    name: {
                                      kind: "Name",
                                      value: "selfApproval",
                                    },
                                  },
                                  {
                                    kind: "Field",
                                    name: { kind: "Name", value: "fallbackId" },
                                  },
                                  {
                                    kind: "Field",
                                    name: { kind: "Name", value: "decidedAt" },
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
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<ProjectReviewsQuery, ProjectReviewsQueryVariables>;
export const ExecuteTaskDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "mutation",
      name: { kind: "Name", value: "ExecuteTask" },
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
              name: { kind: "Name", value: "ExecuteTaskInput" },
            },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "executeTask" },
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
                { kind: "Field", name: { kind: "Name", value: "taskId" } },
                { kind: "Field", name: { kind: "Name", value: "version" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "projectVersion" },
                },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<ExecuteTaskMutation, ExecuteTaskMutationVariables>;
export const ReviewCompletionDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "mutation",
      name: { kind: "Name", value: "ReviewCompletion" },
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
              name: { kind: "Name", value: "ReviewCompletionInput" },
            },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "reviewCompletion" },
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
                { kind: "Field", name: { kind: "Name", value: "taskId" } },
                { kind: "Field", name: { kind: "Name", value: "version" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "projectVersion" },
                },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  ReviewCompletionMutation,
  ReviewCompletionMutationVariables
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
export const OwnerOversightDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "query",
      name: { kind: "Name", value: "OwnerOversight" },
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
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "ownerOversight" },
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
                        name: { kind: "Name", value: "version" },
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
                        name: { kind: "Name", value: "timezone" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "ownerName" },
                      },
                    ],
                  },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "currentDeadline" },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "originalOverdue" },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "currentOverdue" },
                },
                { kind: "Field", name: { kind: "Name", value: "forecastAt" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "forecastState" },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "forecastLate" },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "actualDeliveryAt" },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "escalations" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      { kind: "Field", name: { kind: "Name", value: "id" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "sourceRequestId" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "version" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "reason" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "affectedTeam" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "assessmentState" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "forecastAt" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "assessmentSummary" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "createdAt" },
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
                        name: { kind: "Name", value: "escalationId" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "outcome" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "actorId" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "actorName" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "actorRole" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "reason" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "affectedTeam" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "forecastAt" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "assessmentState" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "previousDeadline" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "revisedDeadline" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "previousOverdue" },
                      },
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
                { kind: "Field", name: { kind: "Name", value: "hasMore" } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<OwnerOversightQuery, OwnerOversightQueryVariables>;
export const ReviewFallbacksDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "query",
      name: { kind: "Name", value: "ReviewFallbacks" },
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
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "reviewFallbacks" },
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
            ],
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "canRecord" } },
                { kind: "Field", name: { kind: "Name", value: "leaderId" } },
                { kind: "Field", name: { kind: "Name", value: "leaderName" } },
                { kind: "Field", name: { kind: "Name", value: "hasMore" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "records" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      { kind: "Field", name: { kind: "Name", value: "id" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "leaderId" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "leaderName" },
                      },
                      { kind: "Field", name: { kind: "Name", value: "scope" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "reason" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "actorId" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "actorName" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "startsAt" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "endsAt" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "createdAt" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "active" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "revokedAt" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "revokedBy" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "revocationReason" },
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
  ReviewFallbacksQuery,
  ReviewFallbacksQueryVariables
>;
export const PreviewOwnerDeadlineDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "mutation",
      name: { kind: "Name", value: "PreviewOwnerDeadline" },
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
              name: { kind: "Name", value: "PreviewOwnerDeadlineInput" },
            },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "previewOwnerDeadline" },
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
                { kind: "Field", name: { kind: "Name", value: "deadlineAt" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "deadlineLocal" },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "originalDeadline" },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "currentDeadline" },
                },
                { kind: "Field", name: { kind: "Name", value: "forecastAt" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "calendarNumber" },
                },
                { kind: "Field", name: { kind: "Name", value: "expiresAt" } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  PreviewOwnerDeadlineMutation,
  PreviewOwnerDeadlineMutationVariables
>;
export const RecordOwnerDecisionDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "mutation",
      name: { kind: "Name", value: "RecordOwnerDecision" },
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
              name: { kind: "Name", value: "RecordOwnerDecisionInput" },
            },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "recordOwnerDecision" },
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
                { kind: "Field", name: { kind: "Name", value: "outcome" } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  RecordOwnerDecisionMutation,
  RecordOwnerDecisionMutationVariables
>;
export const RecordReviewFallbackDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "mutation",
      name: { kind: "Name", value: "RecordReviewFallback" },
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
              name: { kind: "Name", value: "RecordReviewFallbackInput" },
            },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "recordReviewFallback" },
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
                { kind: "Field", name: { kind: "Name", value: "active" } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  RecordReviewFallbackMutation,
  RecordReviewFallbackMutationVariables
>;
export const RevokeReviewFallbackDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "mutation",
      name: { kind: "Name", value: "RevokeReviewFallback" },
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
              name: { kind: "Name", value: "RevokeReviewFallbackInput" },
            },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "revokeReviewFallback" },
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
                { kind: "Field", name: { kind: "Name", value: "active" } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  RevokeReviewFallbackMutation,
  RevokeReviewFallbackMutationVariables
>;
export const ProjectCoordinationDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "query",
      name: { kind: "Name", value: "ProjectCoordination" },
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
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "projectCoordination" },
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
            ],
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                {
                  kind: "Field",
                  name: { kind: "Name", value: "records" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      {
                        kind: "FragmentSpread",
                        name: { kind: "Name", value: "CoordinationFields" },
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
    {
      kind: "FragmentDefinition",
      name: { kind: "Name", value: "CoordinationFields" },
      typeCondition: {
        kind: "NamedType",
        name: { kind: "Name", value: "CoordinationRecord" },
      },
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          { kind: "Field", name: { kind: "Name", value: "id" } },
          { kind: "Field", name: { kind: "Name", value: "projectId" } },
          { kind: "Field", name: { kind: "Name", value: "kind" } },
          { kind: "Field", name: { kind: "Name", value: "topic" } },
          { kind: "Field", name: { kind: "Name", value: "details" } },
          { kind: "Field", name: { kind: "Name", value: "dueAt" } },
          { kind: "Field", name: { kind: "Name", value: "location" } },
          {
            kind: "Field",
            name: { kind: "Name", value: "acknowledgementRequired" },
          },
          { kind: "Field", name: { kind: "Name", value: "version" } },
          { kind: "Field", name: { kind: "Name", value: "createdAt" } },
          { kind: "Field", name: { kind: "Name", value: "overdue" } },
          {
            kind: "Field",
            name: { kind: "Name", value: "recipients" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "accountId" } },
                { kind: "Field", name: { kind: "Name", value: "displayName" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "acknowledgement" },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "responseState" },
                },
              ],
            },
          },
          {
            kind: "Field",
            name: { kind: "Name", value: "followUps" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "id" } },
                { kind: "Field", name: { kind: "Name", value: "actorId" } },
                { kind: "Field", name: { kind: "Name", value: "note" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "nextFollowUpAt" },
                },
                { kind: "Field", name: { kind: "Name", value: "createdAt" } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  ProjectCoordinationQuery,
  ProjectCoordinationQueryVariables
>;
export const CreateCoordinationDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "mutation",
      name: { kind: "Name", value: "CreateCoordination" },
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
              name: { kind: "Name", value: "CreateCoordinationInput" },
            },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "createCoordination" },
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
                  name: { kind: "Name", value: "CoordinationFields" },
                },
              ],
            },
          },
        ],
      },
    },
    {
      kind: "FragmentDefinition",
      name: { kind: "Name", value: "CoordinationFields" },
      typeCondition: {
        kind: "NamedType",
        name: { kind: "Name", value: "CoordinationRecord" },
      },
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          { kind: "Field", name: { kind: "Name", value: "id" } },
          { kind: "Field", name: { kind: "Name", value: "projectId" } },
          { kind: "Field", name: { kind: "Name", value: "kind" } },
          { kind: "Field", name: { kind: "Name", value: "topic" } },
          { kind: "Field", name: { kind: "Name", value: "details" } },
          { kind: "Field", name: { kind: "Name", value: "dueAt" } },
          { kind: "Field", name: { kind: "Name", value: "location" } },
          {
            kind: "Field",
            name: { kind: "Name", value: "acknowledgementRequired" },
          },
          { kind: "Field", name: { kind: "Name", value: "version" } },
          { kind: "Field", name: { kind: "Name", value: "createdAt" } },
          { kind: "Field", name: { kind: "Name", value: "overdue" } },
          {
            kind: "Field",
            name: { kind: "Name", value: "recipients" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "accountId" } },
                { kind: "Field", name: { kind: "Name", value: "displayName" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "acknowledgement" },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "responseState" },
                },
              ],
            },
          },
          {
            kind: "Field",
            name: { kind: "Name", value: "followUps" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "id" } },
                { kind: "Field", name: { kind: "Name", value: "actorId" } },
                { kind: "Field", name: { kind: "Name", value: "note" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "nextFollowUpAt" },
                },
                { kind: "Field", name: { kind: "Name", value: "createdAt" } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  CreateCoordinationMutation,
  CreateCoordinationMutationVariables
>;
export const FollowUpCoordinationDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "mutation",
      name: { kind: "Name", value: "FollowUpCoordination" },
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
              name: { kind: "Name", value: "FollowUpCoordinationInput" },
            },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "followUpCoordination" },
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
                  name: { kind: "Name", value: "CoordinationFields" },
                },
              ],
            },
          },
        ],
      },
    },
    {
      kind: "FragmentDefinition",
      name: { kind: "Name", value: "CoordinationFields" },
      typeCondition: {
        kind: "NamedType",
        name: { kind: "Name", value: "CoordinationRecord" },
      },
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          { kind: "Field", name: { kind: "Name", value: "id" } },
          { kind: "Field", name: { kind: "Name", value: "projectId" } },
          { kind: "Field", name: { kind: "Name", value: "kind" } },
          { kind: "Field", name: { kind: "Name", value: "topic" } },
          { kind: "Field", name: { kind: "Name", value: "details" } },
          { kind: "Field", name: { kind: "Name", value: "dueAt" } },
          { kind: "Field", name: { kind: "Name", value: "location" } },
          {
            kind: "Field",
            name: { kind: "Name", value: "acknowledgementRequired" },
          },
          { kind: "Field", name: { kind: "Name", value: "version" } },
          { kind: "Field", name: { kind: "Name", value: "createdAt" } },
          { kind: "Field", name: { kind: "Name", value: "overdue" } },
          {
            kind: "Field",
            name: { kind: "Name", value: "recipients" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "accountId" } },
                { kind: "Field", name: { kind: "Name", value: "displayName" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "acknowledgement" },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "responseState" },
                },
              ],
            },
          },
          {
            kind: "Field",
            name: { kind: "Name", value: "followUps" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "id" } },
                { kind: "Field", name: { kind: "Name", value: "actorId" } },
                { kind: "Field", name: { kind: "Name", value: "note" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "nextFollowUpAt" },
                },
                { kind: "Field", name: { kind: "Name", value: "createdAt" } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  FollowUpCoordinationMutation,
  FollowUpCoordinationMutationVariables
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
export const ProjectTasksDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "query",
      name: { kind: "Name", value: "ProjectTasks" },
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
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "projectTasks" },
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
                        name: { kind: "Name", value: "version" },
                      },
                    ],
                  },
                },
                { kind: "Field", name: { kind: "Name", value: "canPlan" } },
                { kind: "Field", name: { kind: "Name", value: "hasMore" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "tasks" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      { kind: "Field", name: { kind: "Name", value: "id" } },
                      { kind: "Field", name: { kind: "Name", value: "title" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "status" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "assigneeName" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "details" },
                        selectionSet: {
                          kind: "SelectionSet",
                          selections: [
                            {
                              kind: "Field",
                              name: { kind: "Name", value: "instructions" },
                            },
                            {
                              kind: "Field",
                              name: {
                                kind: "Name",
                                value: "acceptanceCriteria",
                              },
                            },
                            {
                              kind: "Field",
                              name: { kind: "Name", value: "version" },
                            },
                            {
                              kind: "Field",
                              name: { kind: "Name", value: "assigneeId" },
                            },
                            {
                              kind: "Field",
                              name: { kind: "Name", value: "assignedAt" },
                            },
                            {
                              kind: "Field",
                              name: { kind: "Name", value: "history" },
                              selectionSet: {
                                kind: "SelectionSet",
                                selections: [
                                  {
                                    kind: "Field",
                                    name: { kind: "Name", value: "id" },
                                  },
                                  {
                                    kind: "Field",
                                    name: { kind: "Name", value: "action" },
                                  },
                                  {
                                    kind: "Field",
                                    name: { kind: "Name", value: "reason" },
                                  },
                                  {
                                    kind: "Field",
                                    name: { kind: "Name", value: "actorName" },
                                  },
                                  {
                                    kind: "Field",
                                    name: { kind: "Name", value: "before" },
                                  },
                                  {
                                    kind: "Field",
                                    name: { kind: "Name", value: "after" },
                                  },
                                  {
                                    kind: "Field",
                                    name: { kind: "Name", value: "version" },
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
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<ProjectTasksQuery, ProjectTasksQueryVariables>;
export const TaskCandidatesDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "query",
      name: { kind: "Name", value: "TaskCandidates" },
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
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "taskCandidates" },
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
} as unknown as DocumentNode<TaskCandidatesQuery, TaskCandidatesQueryVariables>;
export const ChangeTaskDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "mutation",
      name: { kind: "Name", value: "ChangeTask" },
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
              name: { kind: "Name", value: "ChangeTaskInput" },
            },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "changeTask" },
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
                { kind: "Field", name: { kind: "Name", value: "taskId" } },
                { kind: "Field", name: { kind: "Name", value: "version" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "projectVersion" },
                },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<ChangeTaskMutation, ChangeTaskMutationVariables>;
export const ProjectScheduleDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "query",
      name: { kind: "Name", value: "ProjectSchedule" },
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
            name: { kind: "Name", value: "projectSchedule" },
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
                        name: { kind: "Name", value: "version" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "approvedDeadline" },
                      },
                    ],
                  },
                },
                { kind: "Field", name: { kind: "Name", value: "canPlan" } },
                { kind: "Field", name: { kind: "Name", value: "state" } },
                { kind: "Field", name: { kind: "Name", value: "forecastAt" } },
                { kind: "Field", name: { kind: "Name", value: "timezone" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "calendarNumber" },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "currentDeadline" },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "tasks" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      { kind: "Field", name: { kind: "Name", value: "title" } },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "version" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "status" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "assigneeName" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "plan" },
                        selectionSet: {
                          kind: "SelectionSet",
                          selections: [
                            {
                              kind: "FragmentSpread",
                              name: {
                                kind: "Name",
                                value: "SchedulePointFields",
                              },
                            },
                          ],
                        },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "original" },
                        selectionSet: {
                          kind: "SelectionSet",
                          selections: [
                            {
                              kind: "FragmentSpread",
                              name: {
                                kind: "Name",
                                value: "SchedulePointFields",
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
                  name: { kind: "Name", value: "overlaps" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "taskId" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "otherTaskId" },
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
                        name: { kind: "Name", value: "actorName" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "reason" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "createdAt" },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "before" },
                        selectionSet: {
                          kind: "SelectionSet",
                          selections: [
                            {
                              kind: "FragmentSpread",
                              name: {
                                kind: "Name",
                                value: "ScheduleAnalysisFields",
                              },
                            },
                          ],
                        },
                      },
                      {
                        kind: "Field",
                        name: { kind: "Name", value: "after" },
                        selectionSet: {
                          kind: "SelectionSet",
                          selections: [
                            {
                              kind: "FragmentSpread",
                              name: {
                                kind: "Name",
                                value: "ScheduleAnalysisFields",
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
        ],
      },
    },
    {
      kind: "FragmentDefinition",
      name: { kind: "Name", value: "SchedulePointFields" },
      typeCondition: {
        kind: "NamedType",
        name: { kind: "Name", value: "SchedulePoint" },
      },
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          { kind: "Field", name: { kind: "Name", value: "id" } },
          { kind: "Field", name: { kind: "Name", value: "requestedStart" } },
          { kind: "Field", name: { kind: "Name", value: "duration" } },
          { kind: "Field", name: { kind: "Name", value: "prerequisites" } },
          { kind: "Field", name: { kind: "Name", value: "effectiveStart" } },
          { kind: "Field", name: { kind: "Name", value: "startsAt" } },
          { kind: "Field", name: { kind: "Name", value: "dueAt" } },
          { kind: "Field", name: { kind: "Name", value: "nextHandoff" } },
          { kind: "Field", name: { kind: "Name", value: "adjusted" } },
          { kind: "Field", name: { kind: "Name", value: "readiness" } },
          { kind: "Field", name: { kind: "Name", value: "issue" } },
        ],
      },
    },
    {
      kind: "FragmentDefinition",
      name: { kind: "Name", value: "ScheduleAnalysisFields" },
      typeCondition: {
        kind: "NamedType",
        name: { kind: "Name", value: "ScheduleAnalysis" },
      },
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          { kind: "Field", name: { kind: "Name", value: "state" } },
          { kind: "Field", name: { kind: "Name", value: "forecastAt" } },
          { kind: "Field", name: { kind: "Name", value: "capacityChecked" } },
          {
            kind: "Field",
            name: { kind: "Name", value: "tasks" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                {
                  kind: "FragmentSpread",
                  name: { kind: "Name", value: "SchedulePointFields" },
                },
              ],
            },
          },
          {
            kind: "Field",
            name: { kind: "Name", value: "overlaps" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "taskId" } },
                { kind: "Field", name: { kind: "Name", value: "otherTaskId" } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  ProjectScheduleQuery,
  ProjectScheduleQueryVariables
>;
export const PreviewTaskScheduleDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "mutation",
      name: { kind: "Name", value: "PreviewTaskSchedule" },
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
              name: { kind: "Name", value: "PreviewTaskScheduleInput" },
            },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "previewTaskSchedule" },
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
                { kind: "Field", name: { kind: "Name", value: "validUntil" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "calendarNumber" },
                },
                { kind: "Field", name: { kind: "Name", value: "timezone" } },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "approvedDeadline" },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "exceedsDeadline" },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "before" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      {
                        kind: "FragmentSpread",
                        name: { kind: "Name", value: "ScheduleAnalysisFields" },
                      },
                    ],
                  },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "after" },
                  selectionSet: {
                    kind: "SelectionSet",
                    selections: [
                      {
                        kind: "FragmentSpread",
                        name: { kind: "Name", value: "ScheduleAnalysisFields" },
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
      name: { kind: "Name", value: "SchedulePointFields" },
      typeCondition: {
        kind: "NamedType",
        name: { kind: "Name", value: "SchedulePoint" },
      },
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          { kind: "Field", name: { kind: "Name", value: "id" } },
          { kind: "Field", name: { kind: "Name", value: "requestedStart" } },
          { kind: "Field", name: { kind: "Name", value: "duration" } },
          { kind: "Field", name: { kind: "Name", value: "prerequisites" } },
          { kind: "Field", name: { kind: "Name", value: "effectiveStart" } },
          { kind: "Field", name: { kind: "Name", value: "startsAt" } },
          { kind: "Field", name: { kind: "Name", value: "dueAt" } },
          { kind: "Field", name: { kind: "Name", value: "nextHandoff" } },
          { kind: "Field", name: { kind: "Name", value: "adjusted" } },
          { kind: "Field", name: { kind: "Name", value: "readiness" } },
          { kind: "Field", name: { kind: "Name", value: "issue" } },
        ],
      },
    },
    {
      kind: "FragmentDefinition",
      name: { kind: "Name", value: "ScheduleAnalysisFields" },
      typeCondition: {
        kind: "NamedType",
        name: { kind: "Name", value: "ScheduleAnalysis" },
      },
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          { kind: "Field", name: { kind: "Name", value: "state" } },
          { kind: "Field", name: { kind: "Name", value: "forecastAt" } },
          { kind: "Field", name: { kind: "Name", value: "capacityChecked" } },
          {
            kind: "Field",
            name: { kind: "Name", value: "tasks" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                {
                  kind: "FragmentSpread",
                  name: { kind: "Name", value: "SchedulePointFields" },
                },
              ],
            },
          },
          {
            kind: "Field",
            name: { kind: "Name", value: "overlaps" },
            selectionSet: {
              kind: "SelectionSet",
              selections: [
                { kind: "Field", name: { kind: "Name", value: "taskId" } },
                { kind: "Field", name: { kind: "Name", value: "otherTaskId" } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  PreviewTaskScheduleMutation,
  PreviewTaskScheduleMutationVariables
>;
export const CommitTaskScheduleDocument = {
  kind: "Document",
  definitions: [
    {
      kind: "OperationDefinition",
      operation: "mutation",
      name: { kind: "Name", value: "CommitTaskSchedule" },
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
              name: { kind: "Name", value: "CommitTaskScheduleInput" },
            },
          },
        },
      ],
      selectionSet: {
        kind: "SelectionSet",
        selections: [
          {
            kind: "Field",
            name: { kind: "Name", value: "commitTaskSchedule" },
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
                  kind: "Field",
                  name: { kind: "Name", value: "projectVersion" },
                },
                {
                  kind: "Field",
                  name: { kind: "Name", value: "scheduleVersion" },
                },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  CommitTaskScheduleMutation,
  CommitTaskScheduleMutationVariables
>;
