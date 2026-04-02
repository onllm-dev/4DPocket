import { type ClassValue, clsx } from "clsx";

// Simple cn() without tailwind-merge for now
export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatDate(date: string | Date): string {
  return new Date(date).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function timeAgo(date: string | Date): string {
  const seconds = Math.floor(
    (Date.now() - new Date(date).getTime()) / 1000
  );
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return formatDate(date);
}

/**
 * Returns the Lucide icon component name for a given platform.
 * Consumers should import the named icon from "lucide-react".
 */
export function platformIcon(platform: string): string {
  const icons: Record<string, string> = {
    youtube: "Play",
    reddit: "MessageSquare",
    github: "Github",
    twitter: "Twitter",
    instagram: "Instagram",
    hackernews: "Flame",
    stackoverflow: "HelpCircle",
    medium: "FileText",
    substack: "Mail",
    spotify: "Music",
    generic: "Link",
  };
  return icons[platform.toLowerCase()] ?? "Link";
}

/**
 * Returns the display name for a given platform.
 */
export function platformLabel(platform: string): string {
  const labels: Record<string, string> = {
    youtube: "YouTube",
    reddit: "Reddit",
    github: "GitHub",
    twitter: "Twitter / X",
    instagram: "Instagram",
    hackernews: "Hacker News",
    stackoverflow: "Stack Overflow",
    medium: "Medium",
    substack: "Substack",
    spotify: "Spotify",
    generic: "Web",
  };
  return labels[platform.toLowerCase()] ?? "Web";
}
