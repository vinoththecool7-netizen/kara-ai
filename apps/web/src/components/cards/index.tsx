import dynamic from "next/dynamic";
import { CardSkeleton } from "./CardSkeleton";

export const TaxBreakdownCardLazy = dynamic(
  () =>
    import("./TaxBreakdownCard").then((m) => ({
      default: m.TaxBreakdownCard,
    })),
  { ssr: false },
);

export const RegimeComparisonCardLazy = dynamic(
  () =>
    import("./RegimeComparisonCard").then((m) => ({
      default: m.RegimeComparisonCard,
    })),
  { ssr: false },
);

export const DeductionGapCardLazy = dynamic(
  () =>
    import("./DeductionGapCard").then((m) => ({
      default: m.DeductionGapCard,
    })),
  { ssr: false },
);

export const CapitalGainsCardLazy = dynamic(
  () =>
    import("./CapitalGainsCard").then((m) => ({
      default: m.CapitalGainsCard,
    })),
  { ssr: false },
);

export const ParsedDocumentCard = dynamic(
  () =>
    import("./ParsedDocumentCard").then((m) => ({
      default: m.ParsedDocumentCard,
    })),
  {
    ssr: false,
    loading: () => <CardSkeleton variant="parsed-document" />,
  },
);
