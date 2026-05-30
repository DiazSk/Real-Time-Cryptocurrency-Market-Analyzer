/**
 * Global types lifted from coinpulse (subset). Anything in this file is
 * available without an import — keep it small. Domain-specific types that
 * are only used in a single component should be declared locally instead.
 */

type OHLCData = [number, number, number, number, number];

type Period =
  | "daily"
  | "weekly"
  | "monthly"
  | "3months"
  | "6months"
  | "yearly"
  | "max";

interface DataTableColumn<T> {
  header: React.ReactNode;
  cell: (row: T, index: number) => React.ReactNode;
  headClassName?: string;
  cellClassName?: string;
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  data: T[];
  rowKey: (row: T, index: number) => React.Key;
  tableClassName?: string;
  headerClassName?: string;
  headerRowClassName?: string;
  headerCellClassName?: string;
  bodyRowClassName?: string;
  bodyCellClassName?: string;
}

interface CoinChartProps {
  data?: OHLCData[];
  liveOhlcv?: OHLCData | null;
  coinId: string;
  height?: number;
  children?: React.ReactNode;
  mode?: "historical" | "live";
  initialPeriod?: Period;
  liveInterval?: "1s" | "1m";
  setLiveInterval?: (interval: "1s" | "1m") => void;
}

interface LiveCoinHeaderProps {
  name: string;
  image: string;
  livePrice?: number;
  livePriceChangePercentage24h: number;
  priceChangePercentage30d: number;
  priceChange24h: number;
}

interface ConverterProps {
  symbol: string;
  icon: string;
  priceList: Record<string, number>;
}

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  hasMorePages: boolean;
}
