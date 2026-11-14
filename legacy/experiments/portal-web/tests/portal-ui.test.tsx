import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  PortalCard,
  PortalCardHeader,
  PortalCardTitle,
  PortalCardDescription,
  PortalCardContent,
  PortalButton,
  PortalBadge,
  PortalInput,
  PortalSelect,
  PortalTableContainer,
  PortalTable,
  PortalTableHeader,
  PortalTableBody,
  PortalTableRow,
  PortalTableHead,
  PortalTableCell,
  PortalTableCaption,
  PortalHeading,
  PortalText,
  PortalEyebrow,
  TaskStatusChart,
  CompletionTrendChart,
} from "@/components/portal-ui";
import { PortalPreview } from "@/features/design-system/portal-preview";

describe("Portal UI Visual Foundation (Stage R2)", () => {
  describe("PortalCard", () => {
    it("renders light variant by default with correct data-slot", () => {
      render(
        <PortalCard>
          <PortalCardHeader>
            <PortalCardTitle>Light Title</PortalCardTitle>
            <PortalCardDescription>Light Description</PortalCardDescription>
          </PortalCardHeader>
          <PortalCardContent>Content Area</PortalCardContent>
        </PortalCard>,
      );

      const card = screen
        .getByRole("heading", { name: "Light Title" })
        .closest('[data-slot="portal-card"]');
      expect(card).toBeInTheDocument();
      expect(card).toHaveAttribute("data-variant", "light");
      expect(screen.getByText("Light Description")).toBeInTheDocument();
      expect(screen.getByText("Content Area")).toBeInTheDocument();
    });

    it("renders dark variant with dark styling attributes", () => {
      render(
        <PortalCard variant="dark">
          <PortalCardHeader>
            <PortalCardTitle as="h2">Analytical Panel</PortalCardTitle>
          </PortalCardHeader>
        </PortalCard>,
      );

      const card = screen
        .getByRole("heading", { name: "Analytical Panel" })
        .closest('[data-slot="portal-card"]');
      expect(card).toBeInTheDocument();
      expect(card).toHaveAttribute("data-variant", "dark");
    });
  });

  describe("PortalButton", () => {
    it("renders primary variant with proper text and attributes", () => {
      render(<PortalButton variant="primary">Confirm Action</PortalButton>);
      const button = screen.getByRole("button", { name: "Confirm Action" });
      expect(button).toBeInTheDocument();
      expect(button).not.toBeDisabled();
    });

    it("renders loading state with aria-busy and disables interaction", () => {
      render(
        <PortalButton variant="primary" loading>
          Submitting
        </PortalButton>,
      );
      const button = screen.getByRole("button", { name: "Submitting" });
      expect(button).toHaveAttribute("aria-busy", "true");
      expect(button).toBeDisabled();
    });

    it("renders secondary and quiet variants", () => {
      const { rerender } = render(
        <PortalButton variant="secondary">Secondary</PortalButton>,
      );
      expect(
        screen.getByRole("button", { name: "Secondary" }),
      ).toBeInTheDocument();

      rerender(<PortalButton variant="quiet">Quiet</PortalButton>);
      expect(screen.getByRole("button", { name: "Quiet" })).toBeInTheDocument();
    });
  });

  describe("PortalBadge", () => {
    it("renders semantic status badges with status role", () => {
      render(
        <div>
          <PortalBadge status="in_progress" />
          <PortalBadge status="review" />
          <PortalBadge status="completed" />
          <PortalBadge status="blocked" />
          <PortalBadge status="pending" />
        </div>,
      );

      expect(screen.getByText("In progress")).toBeInTheDocument();
      expect(screen.getByText("Review")).toBeInTheDocument();
      expect(screen.getByText("Completed")).toBeInTheDocument();
      expect(screen.getByText("Blocked")).toBeInTheDocument();
      expect(screen.getByText("Pending")).toBeInTheDocument();
    });

    it("renders with custom children while preserving status styling", () => {
      render(<PortalBadge status="completed">Custom Label</PortalBadge>);
      expect(screen.getByText("Custom Label")).toBeInTheDocument();
    });
  });

  describe("PortalInput & PortalSelect", () => {
    it.each([PortalInput, PortalSelect])(
      "keeps error descriptions valid and preserves caller descriptions",
      (Control) => {
        render(
          <>
            <p id="external-hint">External guidance</p>
            <Control
              label="Field"
              error="Required"
              supportingText="Hint"
              aria-describedby="external-hint"
            />
          </>,
        );
        const control = screen.getByLabelText("Field");
        expect(control).toHaveAttribute("aria-invalid", "true");
        for (const id of control.getAttribute("aria-describedby")!.split(" ")) {
          expect(document.getElementById(id)).not.toBeNull();
        }
        expect(control.getAttribute("aria-describedby")).toContain(
          "external-hint",
        );
      },
    );

    it("renders labelled input with supporting text and required marker", () => {
      render(
        <PortalInput
          label="Project Name"
          required
          supportingText="Enter a unique name"
          defaultValue="Alpha"
        />,
      );

      const input = screen.getByLabelText(/Project Name/);
      expect(input).toBeInTheDocument();
      expect(input).toBeRequired();
      expect(screen.getByText("Enter a unique name")).toBeInTheDocument();
    });

    it("renders input error state with alert role and aria-invalid", () => {
      render(
        <PortalInput
          label="Task Title"
          error="Title cannot be empty"
          defaultValue=""
        />,
      );

      const input = screen.getByLabelText("Task Title");
      expect(input).toHaveAttribute("aria-invalid", "true");
      const alert = screen.getByRole("alert");
      expect(alert).toHaveTextContent("Title cannot be empty");
    });

    it("renders select control with options", () => {
      render(
        <PortalSelect label="Category" defaultValue="opt2">
          <option value="opt1">Option 1</option>
          <option value="opt2">Option 2</option>
        </PortalSelect>,
      );

      const select = screen.getByLabelText("Category");
      expect(select).toBeInTheDocument();
      expect(select).toHaveValue("opt2");
    });
  });

  describe("PortalTable", () => {
    it("renders table structure with caption and container", () => {
      render(
        <PortalTableContainer>
          <PortalTable>
            <PortalTableCaption>Sample test table</PortalTableCaption>
            <PortalTableHeader>
              <PortalTableRow>
                <PortalTableHead>Header 1</PortalTableHead>
              </PortalTableRow>
            </PortalTableHeader>
            <PortalTableBody>
              <PortalTableRow>
                <PortalTableCell>Cell 1</PortalTableCell>
              </PortalTableRow>
            </PortalTableBody>
          </PortalTable>
        </PortalTableContainer>,
      );

      expect(screen.getByRole("table")).toBeInTheDocument();
      expect(screen.getByText("Sample test table")).toBeInTheDocument();
      expect(screen.getByText("Header 1")).toBeInTheDocument();
      expect(screen.getByText("Cell 1")).toBeInTheDocument();
    });
  });

  describe("PortalTypography", () => {
    it("renders headings and text with appropriate levels and styles", () => {
      render(
        <div>
          <PortalEyebrow>Section Tag</PortalEyebrow>
          <PortalHeading level={1}>Heading 1</PortalHeading>
          <PortalText tone="secondary">Supporting text</PortalText>
        </div>,
      );

      expect(screen.getByText("Section Tag")).toBeInTheDocument();
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
        "Heading 1",
      );
      expect(screen.getByText("Supporting text")).toBeInTheDocument();
    });
  });

  describe("TaskStatusChart (Accessible SVG Donut)", () => {
    it("does not draw a data segment for zero tasks", () => {
      const { container } = render(
        <TaskStatusChart
          data={[
            {
              status: "completed",
              label: "Completed",
              count: 0,
              color: "#00c4cc",
            },
          ]}
        />,
      );
      expect(
        container.querySelectorAll("circle[stroke-dasharray]"),
      ).toHaveLength(0);
      expect(screen.getAllByText("0", { selector: "span" })).toHaveLength(2);
    });

    it("renders SVG with accessible label and screen-reader data table", () => {
      render(<TaskStatusChart />);

      const img = screen.getByRole("img");
      expect(img).toBeInTheDocument();
      // Total count in center
      expect(screen.getByText("26")).toBeInTheDocument();
      expect(screen.getByText("Tasks")).toBeInTheDocument();

      // Screen-reader table fallback check
      expect(screen.getByRole("table", { hidden: true })).toBeInTheDocument();
      expect(
        screen.getByText("Task status distribution", { selector: "h4" }),
      ).toBeInTheDocument();
    });

    it("renders custom data points and recalculates total", () => {
      const customData = [
        {
          status: "completed" as const,
          label: "Complete",
          count: 10,
          color: "#00c4cc",
        },
        {
          status: "in_progress" as const,
          label: "In progress",
          count: 5,
          color: "#38bdf8",
        },
      ];
      render(<TaskStatusChart data={customData} />);

      expect(screen.getByText("15")).toBeInTheDocument();
      expect(screen.getByText("(67%)")).toBeInTheDocument();
      expect(screen.getByText("(33%)")).toBeInTheDocument();
    });
  });

  describe("CompletionTrendChart (Accessible SVG Trend)", () => {
    it("renders SVG with accessible label and screen-reader data table", () => {
      render(<CompletionTrendChart />);

      const img = screen.getByRole("img");
      expect(img).toBeInTheDocument();

      // Accessible table check
      expect(screen.getByRole("table", { hidden: true })).toBeInTheDocument();
      expect(
        screen.getByText("Planned versus completed delivery trend", {
          selector: "h4",
        }),
      ).toBeInTheDocument();

      // Legend labels
      expect(screen.getByText("Planned")).toBeInTheDocument();
      expect(screen.getByText("Completed")).toBeInTheDocument();
    });

    it("renders custom dates and trajectory", () => {
      const customTrend = [
        { date: "1 Nov", planned: 5, completed: 4 },
        { date: "2 Nov", planned: 10, completed: 9 },
      ];
      render(<CompletionTrendChart data={customTrend} />);

      expect(
        screen.getByText("1 Nov", { selector: "text" }),
      ).toBeInTheDocument();
      expect(
        screen.getByText("2 Nov", { selector: "text" }),
      ).toBeInTheDocument();
    });
  });

  describe("PortalPreview Component", () => {
    it("renders full preview section without errors and clearly identifies sample data", () => {
      render(<PortalPreview />);

      expect(
        screen.getByRole("heading", { name: "Portal Visual Foundation" }),
      ).toBeInTheDocument();
      expect(screen.getAllByText(/Sample data/i).length).toBeGreaterThan(0);
      expect(screen.getByText("Team Tasks (Sample Data)")).toBeInTheDocument();
      expect(screen.getByText("Buttons & Badges Palette")).toBeInTheDocument();
    });
  });
});
