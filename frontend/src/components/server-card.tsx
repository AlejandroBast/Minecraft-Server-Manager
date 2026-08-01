"use client";

import {
  Archive,
  Cpu,
  Globe,
  Loader2,
  Play,
  Puzzle,
  RotateCcw,
  Square,
  Terminal,
  Timer,
  Trash2,
  TriangleAlert,
  Users,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { BackupsDialog } from "@/components/backups-dialog";
import { ConsoleDialog } from "@/components/console-dialog";

import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { usePolling } from "@/hooks/use-polling";
import { ApiError, api } from "@/lib/api";
import { formatMemory, formatUptime } from "@/lib/format";
import type { Server } from "@/lib/types";

const TYPE_LABELS: Record<Server["type"], string> = {
  vanilla: "Vanilla",
  paper: "Paper",
  purpur: "Purpur",
  spigot: "Spigot",
  fabric: "Fabric",
  forge: "Forge",
  neoforge: "NeoForge",
};

interface ServerCardProps {
  server: Server;
  onChanged: () => void;
}

export function ServerCard({ server, onChanged }: ServerCardProps) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [consoleOpen, setConsoleOpen] = useState(false);
  const [backupsOpen, setBackupsOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [acting, setActing] = useState(false);

  const canStart = server.status === "stopped" || server.status === "error";
  const canStop = server.status === "online" || server.status === "starting";

  async function runAction(action: () => Promise<void>, errorMessage: string) {
    setActing(true);
    try {
      await action();
      onChanged();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : errorMessage);
    } finally {
      setActing(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await api.deleteServer(server.id);
      toast.success(`Servidor «${server.name}» eliminado.`);
      setConfirmOpen(false);
      onChanged();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "No se pudo eliminar el servidor.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <>
      <Card className="transition-colors hover:border-foreground/20">
        <CardHeader>
          <CardTitle className="text-base">{server.name}</CardTitle>
          <CardDescription className="line-clamp-1">{server.motd}</CardDescription>
          <CardAction>
            <StatusBadge status={server.status} />
          </CardAction>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-1.5">
            <Badge variant="secondary">{TYPE_LABELS[server.type]}</Badge>
            <Badge variant="outline">{server.version}</Badge>
            {server.supports_plugins && (
              <Badge variant="outline">
                <Puzzle /> Plugins
              </Badge>
            )}
            {server.supports_mods && (
              <Badge variant="outline">
                <Puzzle /> Mods
              </Badge>
            )}
          </div>

          {server.status === "installing" && <InstallProgressRow serverId={server.id} />}

          {server.status === "error" && server.last_error && (
            <div className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/10 p-2.5 text-xs text-destructive">
              <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
              <p className="line-clamp-3">{server.last_error}</p>
            </div>
          )}

          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Globe className="size-3.5 shrink-0" />
              <dt className="sr-only">Puerto</dt>
              <dd className="text-foreground tabular-nums">{server.port}</dd>
            </div>
            <div className="flex items-center gap-2 text-muted-foreground">
              <Users className="size-3.5 shrink-0" />
              <dt className="sr-only">Jugadores máximos</dt>
              <dd className="text-foreground tabular-nums">{server.max_players}</dd>
            </div>
            <div className="flex items-center gap-2 text-muted-foreground">
              <Cpu className="size-3.5 shrink-0" />
              <dt className="sr-only">Memoria</dt>
              <dd className="text-foreground">
                {formatMemory(server.memory_min_mb)} – {formatMemory(server.memory_max_mb)}
              </dd>
            </div>
            {server.uptime_seconds !== null && (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Timer className="size-3.5 shrink-0" />
                <dt className="sr-only">Tiempo activo</dt>
                <dd className="text-foreground tabular-nums">
                  {formatUptime(server.uptime_seconds)}
                </dd>
              </div>
            )}
          </dl>
        </CardContent>

        <CardFooter className="gap-2">
          {canStop ? (
            <>
              <Button
                size="sm"
                variant="outline"
                disabled={acting}
                onClick={() =>
                  runAction(() => api.stopServer(server.id), "No se pudo detener el servidor.")
                }
              >
                <Square /> Detener
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={acting}
                onClick={() =>
                  runAction(() => api.restartServer(server.id), "No se pudo reiniciar.")
                }
              >
                <RotateCcw /> Reiniciar
              </Button>
            </>
          ) : (
            <Button
              size="sm"
              disabled={acting || !canStart}
              onClick={() =>
                runAction(() => api.startServer(server.id), "No se pudo iniciar el servidor.")
              }
            >
              {acting ? <Loader2 className="animate-spin" /> : <Play />} Iniciar
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={() => setConsoleOpen(true)}>
            <Terminal /> Consola
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setBackupsOpen(true)}>
            <Archive /> Copias
          </Button>
          <Button
            size="icon-sm"
            variant="ghost"
            className="ml-auto text-muted-foreground hover:text-destructive"
            aria-label={`Eliminar ${server.name}`}
            onClick={() => setConfirmOpen(true)}
          >
            <Trash2 />
          </Button>
        </CardFooter>
      </Card>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>¿Eliminar «{server.name}»?</DialogTitle>
            <DialogDescription>
              Se borrará el registro del servidor. Esta acción no se puede deshacer.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)} disabled={deleting}>
              Cancelar
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
              {deleting ? <Loader2 className="animate-spin" /> : <Trash2 />}
              Eliminar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConsoleDialog server={server} open={consoleOpen} onOpenChange={setConsoleOpen} />
      {/* Montado sólo al abrirse: evita consultar los backups de cada tarjeta. */}
      {backupsOpen && (
        <BackupsDialog
          server={server}
          open={backupsOpen}
          onOpenChange={setBackupsOpen}
          onChanged={onChanged}
        />
      )}
    </>
  );
}

const STAGE_LABELS: Record<string, string> = {
  java: "Descargando Java",
  jar: "Descargando el servidor",
  listo: "Instalación completada",
  error: "Error en la instalación",
};

function InstallProgressRow({ serverId }: { serverId: number }) {
  const { data } = usePolling(() => api.installProgress(serverId), 1000);

  return (
    <div className="space-y-1.5 rounded-lg border border-border bg-muted/40 p-2.5">
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <Loader2 className="size-3 animate-spin" />
          {data ? (STAGE_LABELS[data.stage] ?? data.stage) : "Preparando la instalación…"}
        </span>
        {data && data.progress > 0 && (
          <span className="tabular-nums text-muted-foreground">
            {Math.round(data.progress * 100)}%
          </span>
        )}
      </div>
      <Progress value={(data?.progress ?? 0) * 100} />
      {data?.detail && <p className="text-xs text-muted-foreground">{data.detail}</p>}
    </div>
  );
}
