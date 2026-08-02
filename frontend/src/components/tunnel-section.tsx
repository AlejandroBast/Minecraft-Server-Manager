"use client";

import { Copy, ExternalLink, Loader2, Play, Square, Trash2, Waypoints } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { usePolling } from "@/hooks/use-polling";
import { ApiError, api } from "@/lib/api";

/**
 * Acceso desde internet mediante playit.gg.
 *
 * Es la respuesta al CGNAT: el agente abre la conexión hacia afuera y devuelve
 * una dirección pública que los jugadores escriben tal cual en Minecraft, sin
 * instalar nada. La clave se genera en la web de playit.gg, en la cuenta del
 * usuario: la aplicación nunca ve su contraseña.
 */
export function TunnelSection() {
  const [secret, setSecret] = useState("");
  const [busy, setBusy] = useState(false);
  const tunnel = usePolling(api.tunnel, 10000);
  const data = tunnel.data;

  async function run(action: () => Promise<unknown>, okMessage: string) {
    setBusy(true);
    try {
      await action();
      toast.success(okMessage);
      await tunnel.refresh();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "No se pudo completar la acción.");
    } finally {
      setBusy(false);
    }
  }

  if (tunnel.loading && !data) {
    return <Skeleton className="h-40 rounded-lg" />;
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <h3 className="flex items-center gap-2 text-sm font-medium">
          <Waypoints className="size-4" /> Acceso desde internet (túnel)
        </h3>
        {data?.running && <Badge variant="secondary">activo</Badge>}
      </div>

      <p className="text-sm text-muted-foreground">
        Si tu operador usa CGNAT, abrir puertos no sirve. El túnel de playit.gg te da una
        dirección pública y tus amigos sólo tienen que escribirla en Minecraft.
      </p>

      {!data?.secret_configured ? (
        <div className="space-y-3 rounded-lg border border-border p-3">
          <ol className="list-decimal space-y-2 pl-4 text-sm">
            <li>
              Crea tu clave de agente en playit.gg (es gratis).
              <Button variant="outline" size="sm" className="ml-2" asChild>
                <a href={data?.setup_url} target="_blank" rel="noopener noreferrer">
                  <ExternalLink /> Abrir playit.gg
                </a>
              </Button>
            </li>
            <li>Pega aquí la clave que te dé:</li>
          </ol>

          <form
            className="flex gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              void run(() => api.saveTunnelSecret(secret.trim()), "Clave guardada y verificada.")
                .then(() => setSecret(""));
            }}
          >
            <Input
              value={secret}
              onChange={(event) => setSecret(event.target.value)}
              placeholder="Clave del agente"
              type="password"
              autoComplete="off"
              className="font-mono"
            />
            <Button type="submit" disabled={busy || secret.trim().length < 8}>
              {busy ? <Loader2 className="animate-spin" /> : null} Guardar
            </Button>
          </form>
          <p className="text-xs text-muted-foreground">
            La clave se guarda sólo en tu equipo y nunca se muestra de nuevo.
          </p>
        </div>
      ) : (
        <div className="space-y-3 rounded-lg border border-border p-3">
          <div className="flex flex-wrap items-center gap-2">
            {data.running ? (
              <Button
                size="sm"
                variant="outline"
                disabled={busy}
                onClick={() => run(api.stopTunnel, "Túnel detenido.")}
              >
                <Square /> Detener túnel
              </Button>
            ) : (
              <Button
                size="sm"
                disabled={busy}
                onClick={() => run(api.startTunnel, "Túnel iniciado.")}
              >
                {busy ? <Loader2 className="animate-spin" /> : <Play />} Iniciar túnel
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              className="text-muted-foreground hover:text-destructive"
              disabled={busy}
              onClick={() => run(api.deleteTunnelSecret, "Clave eliminada.")}
            >
              <Trash2 /> Quitar clave
            </Button>
          </div>

          {data.addresses.length > 0 ? (
            <ul className="space-y-2">
              {data.addresses.map((item) => {
                const full = item.port ? `${item.address}:${item.port}` : item.address;
                return (
                  <li key={item.address} className="rounded-lg border border-border p-3">
                    <p className="text-xs text-muted-foreground">{item.name}</p>
                    <div className="mt-1 flex items-center gap-2">
                      <code className="flex-1 truncate rounded bg-muted px-2 py-1 font-mono text-sm">
                        {full}
                      </code>
                      <Button
                        size="icon-xs"
                        variant="ghost"
                        aria-label="Copiar dirección"
                        onClick={() => {
                          void navigator.clipboard.writeText(full);
                          toast.success("Dirección copiada: pásasela a tus amigos.");
                        }}
                      >
                        <Copy />
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : null}
        </div>
      )}

      {data?.notes.map((note) => (
        <p key={note} className="text-xs text-muted-foreground">
          {note}
        </p>
      ))}
    </div>
  );
}
