"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import {
  PortalCard,
  PortalCardHeader,
  PortalCardTitle,
  PortalCardDescription,
  PortalCardContent,
  PortalCardFooter,
} from "@/components/portal-ui/portal-card";
import { PortalButton } from "@/components/portal-ui/portal-button";
import {
  PortalBadge,
  type PortalBadgeStatus,
} from "@/components/portal-ui/portal-badge";
import { PortalInput } from "@/components/portal-ui/portal-input";
import { PortalSelect } from "@/components/portal-ui/portal-select";
import {
  PortalTableContainer,
  PortalTable,
  PortalTableHeader,
  PortalTableBody,
  PortalTableRow,
  PortalTableHead,
  PortalTableCell,
  PortalTableCaption,
} from "@/components/portal-ui/portal-table";
import {
  PortalHeading,
  PortalText,
  PortalEyebrow,
} from "@/components/portal-ui/portal-typography";
import { TaskStatusChart } from "@/components/portal-ui/charts/task-status-chart";
import { CompletionTrendChart } from "@/components/portal-ui/charts/completion-trend-chart";
import { portalTokens } from "@/components/portal-ui/portal-tokens";
import { Info, Sparkles } from "lucide-react";

// Local static preview fixtures (Sample data only - no real backend entities)
const sampleTasks = [
  {
    ref: "PRJ-101",
    title: "Account settings portal view",
    assignee: "Maya Fernando",
    status: "in_progress" as PortalBadgeStatus,
    dueDate: "16 Nov",
  },
  {
    ref: "PRJ-102",
    title: "Access permission boundary check",
    assignee: "Dilan Silva",
    status: "review" as PortalBadgeStatus,
    dueDate: "13 Nov",
  },
  {
    ref: "PRJ-103",
    title: "Notification preferences layout",
    assignee: "Nadia Perera",
    status: "completed" as PortalBadgeStatus,
    dueDate: "12 Nov",
  },
  {
    ref: "PRJ-104",
    title: "Export history storage service",
    assignee: "Ravi Kumar",
    status: "blocked" as PortalBadgeStatus,
    dueDate: "18 Nov",
  },
  {
    ref: "PRJ-105",
    title: "Company calendar exceptions",
    assignee: "Assignee pending",
    status: "pending" as PortalBadgeStatus,
    dueDate: "20 Nov",
  },
];

export function PortalPreview() {
  const [btnLoading, setBtnLoading] = React.useState(false);
  const [inputText, setInputText] = React.useState("Customer portal rollout");
  const [hasError, setHasError] = React.useState(false);
  const [validationText, setValidationText] = React.useState("Valid entry");

  return (
    <section
      aria-labelledby="portal-foundation-heading"
      className="portal-theme space-y-8 rounded-3xl bg-[#eef4f8] p-4 sm:p-8 text-[#0f1d2e] border border-[#d6e2ed]"
    >
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#d6e2ed] pb-6">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex size-7 items-center justify-center rounded-lg bg-[#00b4d8] text-[#071626]">
              <Sparkles className="size-4" aria-hidden="true" />
            </span>
            <PortalEyebrow>Stage R2 Architecture</PortalEyebrow>
          </div>
          <PortalHeading
            level={1}
            id="portal-foundation-heading"
            className="mt-1"
          >
            Portal Visual Foundation
          </PortalHeading>
          <PortalText tone="secondary" className="mt-1 max-w-2xl">
            Navy/ocean-blue analytical panels and cyan accents designed for
            role-based portals. Demonstrates tokens, accessible code-native SVG
            charts, and reusable controls.
          </PortalText>
        </div>
        <div className="inline-flex items-center gap-2 rounded-xl border border-cyan-200 bg-cyan-50/80 px-3 py-1.5 text-xs font-medium text-cyan-900 shrink-0 self-start md:self-center">
          <Info className="size-4 text-[#00b4d8]" aria-hidden="true" />
          <span>Sample data · Development preview</span>
        </div>
      </div>

      {/* Analytical Dark Panels & Charts */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <div>
            <PortalHeading level={3} className="text-sm font-semibold">
              Analytical Dark Panels &amp; Charts
            </PortalHeading>
            <PortalText tone="secondary" size="xs">
              Dark panels (<code>variant=&quot;dark&quot;</code>) with
              high-contrast text and accessible SVG charts.
            </PortalText>
          </div>
          <span className="text-[11px] font-medium text-[#52677d]">
            Sample data
          </span>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          {/* Chart 1: Donut Distribution */}
          <PortalCard variant="dark">
            <PortalCardHeader>
              <div className="flex items-center justify-between">
                <PortalCardTitle>Task Status Distribution</PortalCardTitle>
                <PortalBadge status="info" variant="dark">
                  Sample data
                </PortalBadge>
              </div>
              <PortalCardDescription>
                Proportional breakdown of tasks across primary states.
                Code-native SVG with screen-reader summary.
              </PortalCardDescription>
            </PortalCardHeader>
            <PortalCardContent className="pt-2">
              <TaskStatusChart variant="dark" />
            </PortalCardContent>
            <PortalCardFooter className="border-t border-[#1e3a5a] pt-3 text-[11px] text-[#8fa8c6]">
              Accessible: includes hidden data table and distinct
              colors/offsets.
            </PortalCardFooter>
          </PortalCard>

          {/* Chart 2: Planned vs Completed Trend */}
          <PortalCard variant="dark">
            <PortalCardHeader>
              <div className="flex items-center justify-between">
                <PortalCardTitle>Completion Trend</PortalCardTitle>
                <PortalBadge status="info" variant="dark">
                  Sample data
                </PortalBadge>
              </div>
              <PortalCardDescription>
                Target planned trajectory vs. actual delivered tasks over the
                current window.
              </PortalCardDescription>
            </PortalCardHeader>
            <PortalCardContent className="pt-2">
              <CompletionTrendChart variant="dark" />
            </PortalCardContent>
            <PortalCardFooter className="border-t border-[#1e3a5a] pt-3 text-[11px] text-[#8fa8c6]">
              Accessible: dashed purple for target, solid cyan + area fill for
              delivered.
            </PortalCardFooter>
          </PortalCard>
        </div>
      </div>

      {/* Light Working Cards: Table & Form Controls */}
      <div>
        <div className="mb-3">
          <PortalHeading level={3} className="text-sm font-semibold">
            Light Working Surfaces
          </PortalHeading>
          <PortalText tone="secondary" size="xs">
            Clean white cards (<code>variant=&quot;light&quot;</code>) for data
            tables and task administration.
          </PortalText>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Table Container (2 columns on large screens) */}
          <PortalCard variant="light" className="lg:col-span-2">
            <PortalCardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <PortalCardTitle>Team Tasks (Sample Data)</PortalCardTitle>
                  <PortalCardDescription>
                    Responsive data table with subtle headers, row dividers, and
                    status indicators.
                  </PortalCardDescription>
                </div>
                <PortalBadge status="completed" variant="light">
                  5 tasks
                </PortalBadge>
              </div>
            </PortalCardHeader>
            <PortalCardContent>
              <PortalTableContainer variant="light">
                <PortalTable>
                  <PortalTableHeader>
                    <PortalTableRow>
                      <PortalTableHead>Task Ref</PortalTableHead>
                      <PortalTableHead>Task Title</PortalTableHead>
                      <PortalTableHead>Assignee</PortalTableHead>
                      <PortalTableHead>Status</PortalTableHead>
                      <PortalTableHead>Due Date</PortalTableHead>
                    </PortalTableRow>
                  </PortalTableHeader>
                  <PortalTableBody>
                    {sampleTasks.map((task) => (
                      <PortalTableRow key={task.ref}>
                        <PortalTableCell className="font-mono text-xs font-semibold text-[#007791]">
                          {task.ref}
                        </PortalTableCell>
                        <PortalTableCell className="font-medium">
                          {task.title}
                        </PortalTableCell>
                        <PortalTableCell className="text-xs text-[#52677d]">
                          {task.assignee}
                        </PortalTableCell>
                        <PortalTableCell>
                          <PortalBadge status={task.status} variant="light" />
                        </PortalTableCell>
                        <PortalTableCell className="text-xs text-[#52677d]">
                          {task.dueDate}
                        </PortalTableCell>
                      </PortalTableRow>
                    ))}
                  </PortalTableBody>
                  <PortalTableCaption>
                    Illustrative sample table for R2 visual foundation
                    verification.
                  </PortalTableCaption>
                </PortalTable>
              </PortalTableContainer>
            </PortalCardContent>
          </PortalCard>

          {/* Form Controls Column */}
          <PortalCard variant="light" className="space-y-4">
            <PortalCardHeader>
              <PortalCardTitle>Controls &amp; Inputs</PortalCardTitle>
              <PortalCardDescription>
                Labelled controls with focus rings, validation, and error
                states.
              </PortalCardDescription>
            </PortalCardHeader>
            <PortalCardContent className="space-y-4">
              <PortalInput
                label="Project Name"
                required
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                supportingText="Descriptive title for project identification."
              />

              <PortalSelect label="Select Domain Category" defaultValue="web">
                <option value="web">Web Application &amp; Portals</option>
                <option value="api">Backend Services &amp; APIs</option>
                <option value="infra">Infrastructure &amp; Security</option>
              </PortalSelect>

              <PortalInput
                label="Validation Test Input"
                value={validationText}
                error={
                  hasError
                    ? "This field is required for submission."
                    : undefined
                }
                onChange={(e) => {
                  setValidationText(e.target.value);
                  setHasError(e.target.value.length === 0);
                }}
                supportingText="Clear text to trigger validation alert."
              />

              <div className="pt-2">
                <PortalButton
                  variant="secondary"
                  size="sm"
                  onClick={() => setHasError(!hasError)}
                  className="w-full"
                >
                  {hasError ? "Clear Validation Error" : "Simulate Error State"}
                </PortalButton>
              </div>
            </PortalCardContent>
          </PortalCard>
        </div>
      </div>

      {/* Button & Badge Palette */}
      <PortalCard variant="light">
        <PortalCardHeader>
          <PortalCardTitle>Buttons &amp; Badges Palette</PortalCardTitle>
          <PortalCardDescription>
            Core button variants and semantic status badges across light and
            dark themes.
          </PortalCardDescription>
        </PortalCardHeader>
        <PortalCardContent className="space-y-6">
          {/* Button row */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#52677d] mb-3">
              Button Hierarchy
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <PortalButton variant="primary">Primary Action</PortalButton>
              <PortalButton variant="secondary">Secondary Outline</PortalButton>
              <PortalButton variant="quiet">Quiet Text</PortalButton>
              <PortalButton variant="danger">Destructive</PortalButton>
              <PortalButton
                variant="primary"
                loading={btnLoading}
                onClick={() => setBtnLoading(true)}
              >
                {btnLoading ? "Processing…" : "Toggle Loading State"}
              </PortalButton>
              <PortalButton
                variant="secondary"
                onClick={() => setBtnLoading(false)}
              >
                Reset Loading State
              </PortalButton>
              <PortalButton variant="secondary" disabled>
                Disabled
              </PortalButton>
            </div>
          </div>

          {/* Badge row */}
          <div className="border-t border-[#d6e2ed] pt-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#52677d] mb-3">
              Semantic Task Statuses (Light &amp; Dark)
            </p>
            <div className="flex flex-wrap gap-2.5">
              <PortalBadge status="pending" variant="light" />
              <PortalBadge status="in_progress" variant="light" />
              <PortalBadge status="review" variant="light" />
              <PortalBadge status="completed" variant="light" />
              <PortalBadge status="blocked" variant="light" />
            </div>
            <div className="mt-3 flex flex-wrap gap-2.5 rounded-xl bg-[#0d233a] p-3 border border-[#1e3a5a]">
              <PortalBadge status="pending" variant="dark" />
              <PortalBadge status="in_progress" variant="dark" />
              <PortalBadge status="review" variant="dark" />
              <PortalBadge status="completed" variant="dark" />
              <PortalBadge status="blocked" variant="dark" />
            </div>
          </div>

          {/* Swatches */}
          <div className="border-t border-[#d6e2ed] pt-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#52677d] mb-3">
              Core Theme Tokens
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-3">
              {[
                {
                  name: "Dark Panel",
                  hex: portalTokens.colors.surfaceDarkCard,
                  bg: portalTokens.colors.surfaceDarkCard,
                  text: "#fff",
                },
                {
                  name: "Dark Canvas",
                  hex: portalTokens.colors.surfaceDarkCanvas,
                  bg: portalTokens.colors.surfaceDarkCanvas,
                  text: "#fff",
                },
                {
                  name: "Light Canvas",
                  hex: portalTokens.colors.surfaceLightCanvas,
                  bg: portalTokens.colors.surfaceLightCanvas,
                  text: "#0f1d2e",
                },
                {
                  name: "Light Card",
                  hex: portalTokens.colors.surfaceLightCard,
                  bg: portalTokens.colors.surfaceLightCard,
                  text: "#0f1d2e",
                  border: true,
                },
                {
                  name: "Cyan Accent",
                  hex: portalTokens.colors.accentCyan,
                  bg: portalTokens.colors.accentCyan,
                  text: portalTokens.colors.accentCyanForeground,
                },
                {
                  name: "Charcoal Ink",
                  hex: portalTokens.colors.textLightPrimary,
                  bg: portalTokens.colors.textLightPrimary,
                  text: "#fff",
                },
              ].map((swatch) => (
                <div key={swatch.name} className="flex flex-col gap-1.5">
                  <div
                    className={cn(
                      "h-12 rounded-xl flex items-center justify-center text-[10px] font-mono font-medium shadow-xs",
                      swatch.border && "border border-[#d6e2ed]",
                    )}
                    style={{ backgroundColor: swatch.bg, color: swatch.text }}
                  >
                    {swatch.hex}
                  </div>
                  <span className="text-xs font-medium text-[#0f1d2e]">
                    {swatch.name}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </PortalCardContent>
      </PortalCard>
    </section>
  );
}
