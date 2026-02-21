import { cn } from "@/lib/utils";

type Props = { level: "Low" | "Medium" | "High"; className?: string };

export function RiskBadge({ level, className }: Props) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold",
        level === "Low" && "bg-risk-low-bg text-risk-low",
        level === "Medium" && "bg-risk-medium-bg text-risk-medium",
        level === "High" && "bg-risk-high-bg text-risk-high",
        className
      )}
    >
      {level} Risk
    </span>
  );
}
