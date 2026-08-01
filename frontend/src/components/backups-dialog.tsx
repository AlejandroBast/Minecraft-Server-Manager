"use client";

import { Archive, ArchiveRestore, Loader2, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { usePolling } from "@/hooks/use-polling";
import { ApiError, api } from "@/lib/api";
import { formatBytes, formatDateTime } from "@/lib/format";
import type { Backup, BackupStatus, Server } from "@/lib/types";

const STATUS_LABELS: Record<BackupStatus, string> = {
  pending: "Pendiente",
  running: "Creando…",
  completed: "Completada",
  failed: "Fallida",
};

const STATUS_VARIANTS: Record<BackupStatus, "secondary" | "outline" | "destructive"> = {
  pending: "outline",
  running: "outline",
  completed: "secondary",
  failed: "destructive",
};

interface BackupsDialogProps {
  server: Server;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onChanged: () => void;
}

export function BackupsDialog({ server, open, onOpenChange, onChanged }: BackupsDialogProps) {
  const [busy, setBusy] = useState(false);
  const [confirmRestore, setConfirmRestore] = useState<Backup | null>(null);

  // Sondeo cada 2 s mientras el diálogo está abierto: así la copia en curso
  // pasa sola de «Creando…» a «Completada».
  const backups = usePolling(() => api.listBackups(server.id), open ? 2000 : 0);

  async function run(action: () => Promise<unknown>, okMessage: string, errorMessage: string) {
    setBusy(true);
    try {
      await action();
      toast.success(okMessage);
      await backups.refresh();
      onChanged();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : errorMessage);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Archive className="size-4" /> Copias de seguridad — {server.name}
            </DialogTitle>
            <DialogDescription>
              Copias ZIP completas del servidor, incluido el mundo. Se pueden crear con el
              servidor en marcha.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <Button
              disabled={busy || server.status === "installing"}
              onClick={() =>
                run(
                  () => api.createBackup(server.id),
                  "Copia iniciada; puede tardar según el tamaño del mundo.",
                  "No se pudo crear la copia.",
                )
              }
            >
              {busy ? <Loader2 className="animate-spin" /> : <Plus />} Crear copia ahora
            </Button>

            {backups.loading && !backups.data ? (
              <div className="space-y-2">
                <Skeleton className="h-14 rounded-lg" />
                <Skeleton className="h-14 rounded-lg" />
              </div>
            ) : !backups.data || backups.data.length === 0 ? (
              <p className="rounded-lg border border-dashed border-border py-8 text-center text-sm text-muted-foreground">
                Todavía no hay copias de este servidor.
              </p>
            ) : (
              <ul className="space-y-2">
                {backups.data.map((backup) => (
                  <li
                    key={backup.id}
                    className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-3 text-sm"
                  >
                    <div className="min-w-0 flex-1 space-y-0.5">
                      <p className="truncate font-medium" title={backup.file}>
                        {formatDateTime(backup.created_at)}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {backup.status === "completed" && `${formatBytes(backup.size_bytes)} · `}
                        {backup.notes ?? backup.file}
                      </p>
                    </div>
                    <Badge variant={STATUS_VARIANTS[backup.status]}>
                      {backup.status === "running" && (
                        <Loader2 className="size-3 animate-spin" />
                      )}
                      {STATUS_LABELS[backup.status]}
                    </Badge>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={busy || backup.status !== "completed"}
                      title={
                        server.status !== "stopped" && server.status !== "error"
                          ? "Detén el servidor para restaurar."
                          : undefined
                      }
                      onClick={() => setConfirmRestore(backup)}
                    >
                      <ArchiveRestore /> Restaurar
                    </Button>
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      className="text-muted-foreground hover:text-destructive"
                      aria-label="Eliminar copia"
                      disabled={busy || backup.status === "running"}
                      onClick={() =>
                        run(
                          () => api.deleteBackup(backup.id),
                          "Copia eliminada.",
                          "No se pudo eliminar la copia.",
                        )
                      }
                    >
                      <Trash2 />
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={confirmRestore !== null} onOpenChange={() => setConfirmRestore(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>¿Restaurar esta copia?</DialogTitle>
            <DialogDescription>
              El contenido actual del servidor (incluido el mundo) se reemplazará por el de la
              copia del {confirmRestore ? formatDateTime(confirmRestore.created_at) : ""}. Esta
              acción no se puede deshacer.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmRestore(null)} disabled={busy}>
              Cancelar
            </Button>
            <Button
              variant="destructive"
              disabled={busy}
              onClick={() => {
                if (!confirmRestore) return;
                void run(
                  () => api.restoreBackup(confirmRestore.id),
                  "Copia restaurada.",
                  "No se pudo restaurar la copia.",
                ).then(() => setConfirmRestore(null));
              }}
            >
              {busy ? <Loader2 className="animate-spin" /> : <ArchiveRestore />} Restaurar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
