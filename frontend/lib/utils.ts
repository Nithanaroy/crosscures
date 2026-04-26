import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { format, formatDistanceToNow, parseISO } from "date-fns";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  try {
    return format(parseISO(dateStr), "MMM d, yyyy");
  } catch {
    return dateStr;
  }
}

export function formatDatetime(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  try {
    return format(parseISO(dateStr), "MMM d, yyyy 'at' h:mm a");
  } catch {
    return dateStr;
  }
}

export function timeAgo(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  try {
    return formatDistanceToNow(parseISO(dateStr), { addSuffix: true });
  } catch {
    return dateStr;
  }
}

export function severityColor(severity: string): string {
  switch (severity?.toLowerCase()) {
    case "severe": return "text-red-600 bg-red-50 border-red-200";
    case "moderate": return "text-orange-600 bg-orange-50 border-orange-200";
    case "mild": return "text-yellow-600 bg-yellow-50 border-yellow-200";
    default: return "text-gray-600 bg-gray-50 border-gray-200";
  }
}

export function severityBadgeColor(severity: string): string {
  switch (severity?.toLowerCase()) {
    case "severe": return "bg-red-100 text-red-700";
    case "moderate": return "bg-orange-100 text-orange-700";
    case "mild": return "bg-yellow-100 text-yellow-700";
    default: return "bg-gray-100 text-gray-700";
  }
}

export function getInitials(name: string): string {
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

export function daysUntil(dateStr: string): number {
  try {
    const target = parseISO(dateStr);
    const now = new Date();
    const diff = target.getTime() - now.getTime();
    return Math.ceil(diff / (1000 * 60 * 60 * 24));
  } catch {
    return 0;
  }
}
