"use client";

import {
  Check,
  Copy,
  Download,
  ExternalLink,
  Loader2,
  LogIn,
  Network,
  Power,
  UserPlus,
  Zap,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { usePolling } from "@/hooks/use-polling";
import { ApiError, api } from "@/lib/api";

/**
 * Red privada con Tailscale.
 *
 * Alternativa de baja latencia al túnel: conecta a cada jugador directamente
 * contigo en lugar de pasar por un servidor intermedio. La interfaz muestra,
 * jugador a jugador, si la conexión es directa o por relé — ese es el dato que
 * dice si de verdad merece la pena frente al túnel.
 */
export function TailscaleSection() {
  const [busy, setBusy] = useState(false);
  const tailscale = usePolling(api.tailscale, 8000);
  const data = tailscale.data;

  async function run(action: () => Promise<unknown>, okMessage: string) {
    setBusy(true);
    try {
      await action();
      toast.success(okMessage);
      await tailscale.refresh();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "No se pudo completar la acción.");
    } finally {
      setBusy(false);
    }
  }

  async function login() {
    setBusy(true);
    try {
      const result = await api.tailscaleLogin();
      if (result.login_url) {
        window.open(result.login_url, "_blank", "noopener,noreferrer");
        toast.success("Se abrió la página de acceso: entra con tu cuenta.");
      } else {
        toast.info(result.message);
      }
      await tailscale.refresh();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "No se pudo iniciar sesión.");
    } finally {
      setBusy(false);
    }
  }

  if (tailscale.loading && !data) {
    return <Skeleton className="h-40 rounded-lg" />;
  }

  const conectados = data?.peers.filter((peer) => peer.online) ?? [];

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <h3 className="flex items-center gap-2 text-sm font-medium">
          <Network className="size-4" /> Red privada (menos latencia)
        </h3>
        {data?.running && <Badge variant="secondary">conectado</Badge>}
      </div>

      <p className="text-sm text-muted-foreground">
        Conecta a tus amigos directamente contigo en vez de dar un rodeo por otro país. Baja
        mucho el ping, pero cada uno tiene que instalar Tailscale una vez.
      </p>

      <div className="space-y-3 rounded-lg border border-border p-3">
        {!data?.installed ? (
          <>
            <Button
              disabled={busy}
              onClick={() => run(api.installTailscale, "Tailscale instalado.")}
            >
              {busy ? <Loader2 className="animate-spin" /> : <Download />} Instalar Tailscale
            </Button>
            <p className="text-xs text-muted-foreground">
              Windows pedirá permiso de administrador: Tailscale añade un adaptador de red y sin
              eso no puede instalarse. La descarga es la oficial y se comprueba su firma digital.
            </p>
          </>
        ) : data.needs_login || !data.running ? (
          <>
            <div className="flex flex-wrap gap-2">
              <Button disabled={busy} onClick={login}>
                {busy ? <Loader2 className="animate-spin" /> : <LogIn />} Iniciar sesión
              </Button>
              {data.login_url && (
                <Button variant="outline" asChild>
                  <a href={data.login_url} target="_blank" rel="noopener noreferrer">
                    <ExternalLink /> Abrir enlace pendiente
                  </a>
                </Button>
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              Se abrirá la página de Tailscale en tu navegador. La aplicación nunca ve tu
              contraseña.
            </p>
          </>
        ) : (
          <>
            <div>
              <p className="text-xs text-muted-foreground">
                Dirección para tus amigos (con el puerto de tu servidor)
              </p>
              <div className="mt-1 flex items-center gap-2">
                <code className="flex-1 truncate rounded bg-muted px-2 py-1 font-mono text-sm">
                  {data.own_ip}
                </code>
                <Button
                  size="icon-xs"
                  variant="ghost"
                  aria-label="Copiar dirección"
                  onClick={() => {
                    void navigator.clipboard.writeText(data.own_ip ?? "");
                    toast.success("Dirección copiada.");
                  }}
                >
                  <Copy />
                </Button>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" asChild>
                <a href={data.invite_url} target="_blank" rel="noopener noreferrer">
                  <UserPlus /> Invitar amigos
                </a>
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={busy}
                onClick={() => run(api.tailscaleDisconnect, "Tailscale desconectado.")}
              >
                <Power /> Desconectar
              </Button>
            </div>

            {conectados.length > 0 && (
              <ul className="space-y-1.5">
                {conectados.map((peer) => (
                  <li
                    key={peer.ip}
                    className="flex items-center gap-2 rounded-lg border border-border p-2 text-sm"
                  >
                    <span className="min-w-0 flex-1 truncate">{peer.name}</span>
                    {peer.direct ? (
                      <Badge variant="secondary">
                        <Zap /> directa
                      </Badge>
                    ) : (
                      <Badge variant="outline" title={`Relé: ${peer.relay ?? "desconocido"}`}>
                        por relé
                      </Badge>
                    )}
                    <Check className="size-3.5 text-emerald-600 dark:text-emerald-400" />
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>

      {data?.notes.map((note) => (
        <p key={note} className="text-xs text-muted-foreground">
          {note}
        </p>
      ))}
    </div>
  );
}
