/**
 * Color palette -- GitHub dark theme.
 *
 * Single source of truth for all colors used in the TUI.
 */

export const Colors = {
  bg: "#0D1117",
  surface: "#161B22",
  border: "#30363D",
  accent: "#58A6FF",
  green: "#3FB950",
  red: "#F85149",
  yellow: "#D29922",
  purple: "#D2A8FF",
  text: "#E6EDF3",
  muted: "#8B949E",
  dim: "#484F58",
} as const;

export type ColorKey = keyof typeof Colors;

/** Gold gradient for the logo and RPG-style chrome. */
export const LogoColors = [
  "#FFD700",
  "#E8C244",
  "#D4A843",
  "#B8860B",
  "#DAA520",
] as const;

export const ShadowColor = "#5C4400";

/**
 * Gold shimmer gradient used for the "thinking" spinner animation.
 *
 * Pattern: dark-gold -> bright-gold -> white highlight -> bright-gold -> dark-gold.
 */
export const GradientColors = [
  "#8B6914", "#9B7424", "#AB8034", "#BB8C44", "#CB9854",
  "#DAA520", "#E8B830", "#F0C840", "#F5D550", "#FAE060",
  "#FFE870", "#FFED80", "#FFF2A0", "#FFF8C0", "#FFFDE0",
  "#FFFFFF", "#FFFDE0", "#FFF8C0", "#FFF2A0", "#FFED80",
  "#FFE870", "#FAE060", "#F5D550", "#F0C840", "#E8B830",
  "#DAA520", "#CB9854", "#BB8C44", "#AB8034", "#9B7424",
] as const;
