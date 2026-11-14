/**
 * Stage R2: Portal Design Tokens
 * Navy/ocean-blue foundation with cyan/turquoise accents.
 * Scoped specifically for portal interfaces, preserving legacy styles untouched.
 */

export const portalTokens = {
  colors: {
    // Surfaces - Light
    surfaceLightCanvas: "#eef4f8",
    surfaceLightCard: "#ffffff",
    surfaceLightCardMuted: "#f6fafc",
    surfaceLightHeader: "#f0f6fa",
    borderLight: "#d6e2ed",
    borderLightSubtle: "#e8f0f6",

    // Surfaces - Dark (Analytical Panels & Dark Cards)
    surfaceDarkCanvas: "#071626",
    surfaceDarkCard: "#0d233a",
    surfaceDarkCardDeep: "#091929",
    surfaceDarkCardMuted: "#132f4c",
    borderDark: "#1e3a5a",
    borderDarkSubtle: "#142c44",

    // Typography - Light Surface
    textLightPrimary: "#0f1d2e",
    textLightSecondary: "#52677d",
    textLightMuted: "#7e94a8",

    // Typography - Dark Surface
    textDarkPrimary: "#f0f6fc",
    textDarkSecondary: "#8fa8c6",
    textDarkMuted: "#627d98",

    // Accent - Cyan / Turquoise
    accentCyan: "#00b4d8",
    accentCyanHover: "#0096c7",
    accentCyanActive: "#0077b6",
    accentCyanSubtle: "#e0f7fa",
    accentCyanDark: "#007791",
    accentCyanForeground: "#071626",

    // Semantic Statuses
    status: {
      pending: {
        label: "Pending",
        color: "#64748b",
        bgLight: "#f1f5f9",
        borderLight: "#cbd5e1",
        textLight: "#475569",
        bgDark: "rgba(100, 116, 139, 0.2)",
        borderDark: "rgba(100, 116, 139, 0.4)",
        textDark: "#cbd5e1",
      },
      in_progress: {
        label: "In progress",
        color: "#0284c7",
        bgLight: "#e0f2fe",
        borderLight: "#bae6fd",
        textLight: "#0369a1",
        bgDark: "rgba(2, 132, 199, 0.2)",
        borderDark: "rgba(2, 132, 199, 0.4)",
        textDark: "#7dd3fc",
      },
      review: {
        label: "Review",
        color: "#d97706",
        bgLight: "#fef3c7",
        borderLight: "#fde68a",
        textLight: "#b45309",
        bgDark: "rgba(217, 119, 6, 0.2)",
        borderDark: "rgba(217, 119, 6, 0.4)",
        textDark: "#fcd34d",
      },
      completed: {
        label: "Completed",
        color: "#059669",
        bgLight: "#d1fae5",
        borderLight: "#a7f3d0",
        textLight: "#047857",
        bgDark: "rgba(5, 150, 105, 0.2)",
        borderDark: "rgba(5, 150, 105, 0.4)",
        textDark: "#6ee7b7",
      },
      blocked: {
        label: "Blocked",
        color: "#e11d48",
        bgLight: "#ffe4e6",
        borderLight: "#fecdd3",
        textLight: "#be123c",
        bgDark: "rgba(225, 29, 72, 0.2)",
        borderDark: "rgba(225, 29, 72, 0.4)",
        textDark: "#fda4af",
      },
    },

    // Chart Palette (Distinguishable by color, pattern, and markers)
    charts: {
      cyan: "#00c4cc",
      blue: "#38bdf8",
      purple: "#818cf8",
      coral: "#f87171",
      mint: "#34d399",
      slate: "#94a3b8",
      gridDark: "rgba(255, 255, 255, 0.08)",
      gridLight: "rgba(15, 29, 46, 0.08)",
    },
  },

  radii: {
    card: "1rem", // 16px
    inner: "0.75rem", // 12px
    control: "0.625rem", // 10px
    badge: "0.375rem", // 6px
    pill: "9999px",
  },

  shadows: {
    cardLight:
      "0 2px 8px -2px rgba(13, 35, 58, 0.06), 0 1px 3px 0 rgba(13, 35, 58, 0.03)",
    cardDark: "0 4px 16px -4px rgba(7, 22, 38, 0.35)",
    glowCyan: "0 0 12px rgba(0, 180, 216, 0.35)",
  },
} as const;

export type PortalStatusKey = keyof typeof portalTokens.colors.status;
