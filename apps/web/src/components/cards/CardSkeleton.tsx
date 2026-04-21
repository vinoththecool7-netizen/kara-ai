import { Skeleton } from "@/components/ui/skeleton";
import {
  Card,
  CardContent,
  CardHeader,
} from "@/components/ui/card";

type Variant = "tax" | "regime" | "deduction" | "capital";

const labels: Record<Variant, string> = {
  tax: "Loading tax breakdown",
  regime: "Loading regime comparison",
  deduction: "Loading deduction gaps",
  capital: "Loading capital gains",
};

const bodyHeights: Record<Variant, string> = {
  tax: "h-48",
  regime: "h-40",
  deduction: "h-36",
  capital: "h-44",
};

interface CardSkeletonProps {
  variant: Variant;
}

export function CardSkeleton({ variant }: CardSkeletonProps) {
  return (
    <Card
      aria-busy="true"
      aria-label={labels[variant]}
      className="border-dashed"
    >
      <CardHeader>
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-3 w-60 mt-1" />
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="grid grid-cols-3 gap-3">
          <div className="space-y-2">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-6 w-24" />
          </div>
          <div className="space-y-2">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-6 w-24" />
          </div>
          <div className="space-y-2">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-6 w-24" />
          </div>
        </div>
        <Skeleton className={`w-full ${bodyHeights[variant]}`} />
      </CardContent>
    </Card>
  );
}
