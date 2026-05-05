import { Skeleton } from "@/components/ui/skeleton";
import {
  Card,
  CardContent,
  CardHeader,
} from "@/components/ui/card";

type Variant = "tax" | "regime" | "deduction" | "capital" | "parsed-document";

const labels: Record<Variant, string> = {
  tax: "Loading tax breakdown",
  regime: "Loading regime comparison",
  deduction: "Loading deduction gaps",
  capital: "Loading capital gains",
  "parsed-document": "Loading parsed document",
};

const bodyHeights: Record<Variant, string> = {
  tax: "h-48",
  regime: "h-40",
  deduction: "h-36",
  capital: "h-44",
  "parsed-document": "h-24",
};

interface CardSkeletonProps {
  variant: Variant;
}

export function CardSkeleton({ variant }: CardSkeletonProps) {
  if (variant === "parsed-document") {
    return (
      <Card
        aria-busy="true"
        aria-label={labels[variant]}
        className="border-dashed"
      >
        <CardHeader>
          {/* Badge placeholder + title */}
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 space-y-2">
              <Skeleton className="h-5 w-48" />
              <Skeleton className="h-3 w-36 mt-1" />
            </div>
            <Skeleton className="h-5 w-16 rounded-full shrink-0" />
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {/* Two amount rows */}
          <div className="grid grid-cols-2 gap-x-6 gap-y-3">
            <div className="space-y-1.5">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-5 w-28" />
            </div>
            <div className="space-y-1.5">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-5 w-28" />
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

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
