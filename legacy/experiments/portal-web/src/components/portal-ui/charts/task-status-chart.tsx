import * as React from "react";
import { cn } from "@/lib/utils";

export interface TaskStatusDataPoint {
  status:
    | "completed"
    | "in_progress"
    | "review"
    | "blocked"
    | "pending"
    | "cancelled";
  label: string;
  count: number;
  color: string;
  dashArray?: string;
}

export interface TaskStatusChartProps {
  data?: TaskStatusDataPoint[];
  variant?: "light" | "dark";
  className?: string;
  title?: string;
}

const defaultStatusData: TaskStatusDataPoint[] = [
  {
    status: "completed",
    label: "Complete",
    count: 18,
    color: "#00c4cc", // Cyan / turquoise
  },
  {
    status: "in_progress",
    label: "In progress",
    count: 4,
    color: "#38bdf8", // Sky blue
  },
  {
    status: "review",
    label: "Review",
    count: 3,
    color: "#818cf8", // Indigo / purple
  },
  {
    status: "blocked",
    label: "Blocked",
    count: 1,
    color: "#f87171", // Coral / red
  },
];

function computeSegments(
  data: TaskStatusDataPoint[],
  total: number,
  circumference: number,
) {
  let accumulatedPercent = 0;
  return data.map((item) => {
    const percent = total > 0 ? item.count / total : 0;
    const strokeDasharray = `${percent * circumference} ${circumference}`;
    // SVG stroke starts at 3 o'clock; rotate by -90deg to start at 12 o'clock
    const strokeDashoffset = -accumulatedPercent * circumference;
    accumulatedPercent += percent;

    return {
      ...item,
      percent: Math.round(percent * 100),
      strokeDasharray,
      strokeDashoffset,
    };
  });
}

export function TaskStatusChart({
  data = defaultStatusData,
  variant = "dark",
  className,
  title = "Task status distribution",
}: TaskStatusChartProps) {
  const chartId = React.useId();
  const summaryId = `task-chart-summary-${chartId}`;

  const total = React.useMemo(() => {
    return data.reduce((sum, item) => sum + item.count, 0);
  }, [data]);

  // SVG Donut geometry
  const size = 160;
  const strokeWidth = 18;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const center = size / 2;

  // Calculate arc offsets for SVG stroke-dasharray
  const segments = React.useMemo(() => {
    return computeSegments(data, total, circumference);
  }, [data, total, circumference]);

  return (
    <div
      data-slot="task-status-chart"
      className={cn(
        "flex flex-col sm:flex-row items-center justify-between gap-6 w-full",
        className,
      )}
    >
      {/* Screen-reader accessible data equivalent */}
      <div id={summaryId} className="sr-only">
        <h4>{title}</h4>
        <p>Total tasks: {total}. Breakdown by status:</p>
        <table>
          <thead>
            <tr>
              <th scope="col">Status</th>
              <th scope="col">Count</th>
              <th scope="col">Percentage</th>
            </tr>
          </thead>
          <tbody>
            {segments.map((item) => (
              <tr key={item.status}>
                <td>{item.label}</td>
                <td>{item.count}</td>
                <td>{item.percent}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* SVG Donut Visual */}
      <div className="relative shrink-0 flex items-center justify-center">
        <svg
          role="img"
          aria-labelledby={summaryId}
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          className="transform -rotate-90"
        >
          {/* Base track */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="transparent"
            stroke={
              variant === "dark"
                ? "rgba(255, 255, 255, 0.08)"
                : "rgba(15, 29, 46, 0.08)"
            }
            strokeWidth={strokeWidth}
          />
          {/* Status segments */}
          {segments
            .filter((segment) => segment.count > 0)
            .map((seg) => (
              <circle
                key={seg.status}
                cx={center}
                cy={center}
                r={radius}
                fill="transparent"
                stroke={seg.color}
                strokeWidth={strokeWidth}
                strokeDasharray={seg.strokeDasharray}
                strokeDashoffset={seg.strokeDashoffset}
                strokeLinecap="round"
                className="transition-all duration-500 ease-out"
              />
            ))}
        </svg>

        {/* Center label */}
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none">
          <span
            className={cn(
              "text-2xl font-bold tracking-tight leading-none",
              variant === "dark" ? "text-white" : "text-[#0f1d2e]",
            )}
          >
            {total}
          </span>
          <span
            className={cn(
              "text-xs font-medium tracking-normal mt-1",
              variant === "dark" ? "text-[#8fa8c6]" : "text-[#52677d]",
            )}
          >
            Tasks
          </span>
        </div>
      </div>

      {/* Legend with explicit text and distinct visual indicators */}
      <div className="flex flex-col gap-2.5 w-full max-w-[180px]">
        {segments.map((item) => (
          <div
            key={item.status}
            className="flex items-center justify-between text-xs font-medium"
          >
            <div className="flex items-center gap-2">
              <span
                className="size-2.5 rounded-full shrink-0"
                style={{ backgroundColor: item.color }}
                aria-hidden="true"
              />
              <span
                className={cn(
                  variant === "dark" ? "text-[#f0f6fc]" : "text-[#0f1d2e]",
                )}
              >
                {item.label}
              </span>
            </div>
            <div className="flex items-center gap-1.5 font-semibold">
              <span
                className={cn(
                  variant === "dark" ? "text-white" : "text-[#0f1d2e]",
                )}
              >
                {item.count}
              </span>
              <span
                className={cn(
                  "text-[10px] font-normal",
                  variant === "dark" ? "text-[#8fa8c6]" : "text-[#7e94a8]",
                )}
              >
                ({item.percent}%)
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
