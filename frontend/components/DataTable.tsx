import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

/** Generic hairline table used by the CoinGecko tiles and exchange listings. */
const DataTable = <T,>({
  columns,
  data,
  rowKey,
  tableClassName,
  headerClassName,
  headerRowClassName,
  headerCellClassName,
  bodyRowClassName,
  bodyCellClassName,
}: DataTableProps<T>) => {
  return (
    <Table className={tableClassName}>
      <TableHeader className={headerClassName}>
        <TableRow className={cn("hover:bg-transparent", headerRowClassName)}>
          {columns.map((column, i) => (
            <TableHead
              key={i}
              className={cn(
                "caption h-9 font-normal first:pl-0 last:pr-0",
                headerCellClassName,
                column.headClassName,
              )}
            >
              {column.header}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.map((row, rowIndex) => (
          <TableRow key={rowKey(row, rowIndex)} className={cn("relative", bodyRowClassName)}>
            {columns.map((column, columnIndex) => (
              <TableCell
                key={columnIndex}
                className={cn("py-3 first:pl-0 last:pr-0", bodyCellClassName, column.cellClassName)}
              >
                {column.cell(row, rowIndex)}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
};

export default DataTable;
