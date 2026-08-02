"use client";

import { Loader2, Package, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { usePolling } from "@/hooks/use-polling";
import { ApiError, api } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AddonKind, Server } from "@/lib/types";

const KIND_LABELS: Record<AddonKind, { title: string; hint: string }> = {
  plugins: {
    title: "Plugins",
    hint: "Los cambios se aplican al reiniciar el servidor.",
  },
  mods: {
    title: "Mods",
    hint: "Los jugadores suelen necesitar el mismo mod instalado. Se aplican al reiniciar.",
  },
};

interface AddonsDialogProps {
  server: Server;
  kind: AddonKind;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AddonsDialog({ server, kind, open, onOpenChange }: AddonsDialogProps) {
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const addons = usePolling(() => api.listAddons(server.id, kind), 0);

  async function uploadFiles(files: FileList | File[]) {
    const jars = [...files];
    if (jars.length === 0) return;
    setBusy(true);
    try {
      for (const file of jars) {
        try {
          const uploaded = await api.uploadAddon(server.id, kind, file);
          toast.success(`«${uploaded.file}» añadido.`);
        } catch (error) {
          toast.error(
            error instanceof ApiError ? error.message : `No se pudo subir «${file.name}».`,
          );
        }
      }
      await addons.refresh();
    } finally {
      setBusy(false);
    }
  }

  async function run(action: () => Promise<unknown>, errorMessage: string) {
    setBusy(true);
    try {
      await action();
      await addons.refresh();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : errorMessage);
    } finally {
      setBusy(false);
    }
  }

  const labels = KIND_LABELS[kind];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Package className="size-4" /> {labels.title} — {server.name}
          </DialogTitle>
          <DialogDescription>{labels.hint}</DialogDescription>
        </DialogHeader>

        {/* Zona para adjuntar: clic o arrastrar y soltar. Nunca hay que abrir
            la carpeta del servidor a mano. */}
        <button
          type="button"
          disabled={busy}
          onClick={() => inputRef.current?.click()}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            void uploadFiles(event.dataTransfer.files);
          }}
          className={cn(
            "flex w-full flex-col items-center gap-2 rounded-xl border-2 border-dashed p-8 text-sm transition-colors",
            dragging
              ? "border-primary bg-primary/5 text-foreground"
              : "border-border text-muted-foreground hover:border-foreground/40",
          )}
        >
          {busy ? <Loader2 className="size-6 animate-spin" /> : <Upload className="size-6" />}
          <span className="font-medium text-foreground">
            Arrastra los .jar aquí o haz clic para elegirlos
          </span>
          <span className="text-xs">Máximo 200 MB por archivo</span>
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".jar"
          multiple
          hidden
          onChange={(event) => {
            if (event.target.files) void uploadFiles(event.target.files);
            event.target.value = "";
          }}
        />

        {addons.loading && !addons.data ? (
          <Skeleton className="h-24 rounded-lg" />
        ) : !addons.data || addons.data.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border py-6 text-center text-sm text-muted-foreground">
            Este servidor todavía no tiene {labels.title.toLowerCase()}.
          </p>
        ) : (
          <ul className="space-y-2">
            {addons.data.map((addon) => (
              <li
                key={addon.file}
                className="flex items-center gap-3 rounded-lg border border-border p-3 text-sm"
              >
                <div className="min-w-0 flex-1">
                  <p
                    className={cn("truncate font-medium", !addon.enabled && "line-through")}
                    title={addon.file}
                  >
                    {addon.file}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatBytes(addon.size_bytes)}
                    {!addon.enabled && " · desactivado"}
                  </p>
                </div>
                <Switch
                  checked={addon.enabled}
                  disabled={busy}
                  aria-label={addon.enabled ? "Desactivar" : "Activar"}
                  onCheckedChange={(enabled) =>
                    run(
                      () => api.toggleAddon(server.id, kind, addon.file, enabled),
                      "No se pudo cambiar el estado.",
                    )
                  }
                />
                <Button
                  size="icon-sm"
                  variant="ghost"
                  className="text-muted-foreground hover:text-destructive"
                  aria-label={`Eliminar ${addon.file}`}
                  disabled={busy}
                  onClick={() =>
                    run(
                      () => api.deleteAddon(server.id, kind, addon.file),
                      "No se pudo eliminar.",
                    )
                  }
                >
                  <Trash2 />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  );
}
