import * as React from "react";
import { cn } from "@/lib/utils";

export interface TrendDataPoint {
  date: string; // e.g. "9 Nov"
  planned: number;
  completed: number;
}

export interface CompletionTrendChartProps {
  data?: TrendDataPoint[];
  variant?: "light" | "dark";
  className?: string;
  title?: string;
}

const defaultTrendData: TrendDataPoint[] = [
  { date: "9 Nov", planned: 8, completed: 5 },
  { date: "10 Nov", planned: 12, completed: 9 },
  { date: "11 Nov", planned: 17, completed: 13 },
  { date: "12 Nov", planned: 21, completed: 17 },
  { date: "13 Nov", planned: 25, completed: 22 },
];

export function CompletionTrendChart({
  data = defaultTrendData,
  variant = "dark",
  className,
  title = "Planned versus completed delivery trend",
}: CompletionTrendChartProps) {
  const chartId = React.useId();
  const summaryId = `trend-chart-summary-${chartId}`;
  const gradientId = `trend-cyan-gradient-${chartId}`;

  // SVG dimensions & margins
  const width = 360;
  const height = 160;
  const paddingLeft = 32;
  const paddingRight = 16;
  const paddingTop = 20;
  const paddingBottom = 28;

  const chartWidth = width - paddingLeft - paddingRight;
  const chartHeight = height - paddingTop - paddingBottom;

  // Max value calculation for Y-scale
  const maxValue = React.useMemo(() => {
    const maxData = Math.max(
      ...data.map((d) => Math.max(d.planned, d.completed)),
      10,
    );
    return Math.ceil(maxData / 5) * 5; // Round up to nearest 5
  }, [data]);

  // Point mapping helpers
  const getX = (index: number) => {
    if (data.length <= 1) return paddingLeft + chartWidth / 2;
    return paddingLeft + (index / (data.length - 1)) * chartWidth;
  };

  const getY = (val: number) => {
    return paddingTop + chartHeight - (val / maxValue) * chartHeight;
  };

  // Build SVG path strings
  const plannedPoints = data
    .map((d, i) => `${getX(i)},${getY(d.planned)}`)
    .join(" ");
  const completedPoints = data
    .map((d, i) => `${getX(i)},${getY(d.completed)}`)
    .join(" ");

  // Closed area polygon under completed line for gradient
  const areaPoints = [
    `${getX(0)},${paddingTop + chartHeight}`,
    ...data.map((d, i) => `${getX(i)},${getY(d.completed)}`),
    `${getX(data.length - 1)},${paddingTop + chartHeight}`,
  ].join(" ");

  // Y-axis tick values (0, mid, max)
  const yTicks = [0, Math.round(maxValue / 2), maxValue];

  return (
    <div
      data-slot="completion-trend-chart"
      className={cn("flex flex-col gap-3 w-full", className)}
    >
      {/* Screen-reader accessible data equivalent */}
      <div id={summaryId} className="sr-only">
        <h4>{title}</h4>
        <p>
          Delivery trend tracking planned commitments versus completed tasks:
        </p>
        <table>
          <thead>
            <tr>
              <th scope="col">Date</th>
              <th scope="col">Planned Target</th>
              <th scope="col">Completed Actual</th>
            </tr>
          </thead>
          <tbody>
            {data.map((item) => (
              <tr key={item.date}>
                <td>{item.date}</td>
                <td>{item.planned} tasks</td>
                <td>{item.completed} tasks</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* SVG Chart Visual */}
      <div className="w-full overflow-hidden">
        <svg
          role="img"
          aria-labelledby={summaryId}
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-auto"
        >
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop
                offset="0%"
                stopColor="#00c4cc"
                stopOpacity={variant === "dark" ? "0.35" : "0.2"}
              />
              <stop offset="100%" stopColor="#00c4cc" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines & Y-axis labels */}
          {yTicks.map((val) => {
            const y = getY(val);
            return (
              <g key={val}>
                <line
                  x1={paddingLeft}
                  y1={y}
                  x2={width - paddingRight}
                  y2={y}
                  stroke={
                    variant === "dark"
                      ? "rgba(255, 255, 255, 0.08)"
                      : "rgba(15, 29, 46, 0.08)"
                  }
                  strokeDasharray={val === 0 ? undefined : "3 3"}
                />
                <text
                  x={paddingLeft - 8}
                  y={y + 3}
                  textAnchor="end"
                  fill={variant === "dark" ? "#8fa8c6" : "#7e94a8"}
                  fontSize="10"
                  fontFamily="inherit"
                >
                  {val}
                </text>
              </g>
            );
          })}

          {/* X-axis date labels */}
          {data.map((d, i) => {
            const x = getX(i);
            return (
              <text
                key={d.date}
                x={x}
                y={height - 6}
                textAnchor="middle"
                fill={variant === "dark" ? "#8fa8c6" : "#52677d"}
                fontSize="10"
                fontFamily="inherit"
              >
                {d.date}
              </text>
            );
          })}

          {/* Completed Area Fill */}
          <polygon points={areaPoints} fill={`url(#${gradientId})`} />

          {/* Planned Line (Dashed Purple) */}
          <polyline
            points={plannedPoints}
            fill="none"
            stroke="#818cf8"
            strokeWidth="2"
            strokeDasharray="4 3"
          />

          {/* Completed Line (Solid Cyan) */}
          <polyline
            points={completedPoints}
            fill="none"
            stroke="#00c4cc"
            strokeWidth="2.5"
            strokeLinecap="round"
          />

          {/* Planned markers (Open purple circles) */}
          {data.map((d, i) => (
            <circle
              key={`planned-${d.date}`}
              cx={getX(i)}
              cy={getY(d.planned)}
              r="3.5"
              fill={variant === "dark" ? "#0d233a" : "#ffffff"}
              stroke="#818cf8"
              strokeWidth="2"
            />
          ))}

          {/* Completed markers (Filled cyan circles) */}
          {data.map((d, i) => (
            <circle
              key={`completed-${d.date}`}
              cx={getX(i)}
              cy={getY(d.completed)}
              r="4"
              fill="#00c4cc"
              stroke={variant === "dark" ? "#0d233a" : "#ffffff"}
              strokeWidth="1.5"
            />
          ))}
        </svg>
      </div>

      {/* Accessible Legend with distinct pattern explanations */}
      <div className="flex items-center justify-center gap-6 pt-1 text-xs">
        <div className="flex items-center gap-2">
          <span
            className="inline-block w-4 h-0.5 border-t-2 border-dashed border-[#818cf8]"
            aria-hidden="true"
          />
          <span
            className={cn(
              "font-medium",
              variant === "dark" ? "text-[#f0f6fc]" : "text-[#0f1d2e]",
            )}
          >
            Planned
          </span>
          <span className="text-[10px] text-[#7e94a8]">(Target)</span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className="inline-block w-4 h-0.5 bg-[#00c4cc]"
            aria-hidden="true"
          />
          <span
            className={cn(
              "font-medium",
              variant === "dark" ? "text-[#f0f6fc]" : "text-[#0f1d2e]",
            )}
          >
            Completed
          </span>
          <span className="text-[10px] text-[#7e94a8]">(Delivered)</span>
        </div>
      </div>
    </div>
  );
}
