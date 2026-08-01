import { cn } from "@/lib/utils";
import type { ServerStatus } from "@/lib/types";

const STATUS_LABELS: Record<ServerStatus, string> = {
  stopped: "Detenido",
  starting: "Iniciando",
  online: "En línea",
  stopping: "Deteniendo",
  restarting: "Reiniciando",
  saving: "Guardando",
  installing: "Instalando",
  error: "Error",
};

const STATUS_STYLES: Record<ServerStatus, string> = {
  stopped: "bg-muted text-muted-foreground",
  starting: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  online: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  stopping: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  restarting: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  saving: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  installing: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  error: "bg-destructive/15 text-destructive",
};

const PULSING: ServerStatus[] = ["starting", "stopping", "restarting", "saving", "installing"];

export function StatusBadge({ status }: { status: ServerStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
        STATUS_STYLES[status],
      )}
    >
      <span
        className={cn(
          "size-1.5 rounded-full bg-current",
          PULSING.includes(status) && "animate-pulse",
        )}
      />
      {STATUS_LABELS[status]}
    </span>
  );
}
