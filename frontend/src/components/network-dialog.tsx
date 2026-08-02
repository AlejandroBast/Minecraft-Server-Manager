"use client";

import { Check, Copy, Globe, Loader2, Lock, LockOpen, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { TunnelSection } from "@/components/tunnel-section";
import { Skeleton } from "@/components/ui/skeleton";
import { usePolling } from "@/hooks/use-polling";
import { ApiError, api } from "@/lib/api";
import type { DnsRecord } from "@/lib/types";

interface NetworkDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function NetworkDialog({ open, onOpenChange }: NetworkDialogProps) {
  const [busy, setBusy] = useState(false);
  const [domain, setDomain] = useState("");
  const [records, setRecords] = useState<DnsRecord[] | null>(null);
  const network = usePolling(api.network, 0);

  async function togglePort(port: number, opening: boolean) {
    setBusy(true);
    try {
      const result = opening ? await api.openPort(port) : await api.closePort(port);
      // El backend responde 200 con success=false cuando el router no coopera:
      // es información para el usuario, no un error de la petición.
      if (result.success) {
        toast.success(result.message);
      } else {
        toast.warning(result.message, { duration: 10000 });
      }
      await network.refresh();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "No se pudo cambiar el puerto.");
    } finally {
      setBusy(false);
    }
  }

  async function requestDns(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!domain.trim()) return;
    setBusy(true);
    try {
      const port = network.data?.ports[0]?.port ?? 25565;
      const result = await api.dnsInstructions(domain.trim(), port);
      setRecords(result.records);
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Dominio no válido.");
    } finally {
      setBusy(false);
    }
  }

  const data = network.data;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Globe className="size-4" /> Red y acceso desde internet
          </DialogTitle>
          <DialogDescription>
            Comparte la IP con tus amigos y abre el puerto sin entrar en la configuración del
            router.
          </DialogDescription>
        </DialogHeader>

        {network.loading && !data ? (
          <Skeleton className="h-48 rounded-lg" />
        ) : !data ? (
          <p className="text-sm text-muted-foreground">No se pudo obtener el estado de la red.</p>
        ) : (
          <div className="space-y-5">
            <div className="grid gap-3 sm:grid-cols-2">
              <AddressRow label="IP local (misma casa o wifi)" value={data.local_ip} />
              <AddressRow label="IP pública (desde internet)" value={data.public_ip} />
            </div>

            {data.notes.map((note) => (
              <div
                key={note}
                className="flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-400"
              >
                <TriangleAlert className="mt-0.5 size-4 shrink-0" />
                <p>{note}</p>
              </div>
            ))}

            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-medium">Puertos</h3>
                <Badge variant={data.upnp_available ? "secondary" : "outline"}>
                  {data.upnp_available ? "UPnP disponible" : "Sin UPnP"}
                </Badge>
              </div>

              {data.ports.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No hay servidores creados todavía.
                </p>
              ) : (
                <ul className="space-y-2">
                  {data.ports.map((port) => (
                    <li
                      key={port.port}
                      className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-3 text-sm"
                    >
                      <span className="font-mono tabular-nums">{port.port}</span>
                      <Badge variant={port.listening ? "secondary" : "outline"}>
                        {port.listening ? "escuchando" : "sin uso"}
                      </Badge>
                      {port.upnp_mapped && (
                        <Badge variant="secondary">
                          <Check /> abierto en el router
                        </Badge>
                      )}
                      <div className="ml-auto flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={busy}
                          onClick={() => togglePort(port.port, true)}
                        >
                          <LockOpen /> Abrir
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={busy || !port.upnp_mapped}
                          onClick={() => togglePort(port.port, false)}
                        >
                          <Lock /> Cerrar
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <Separator />

            <TunnelSection />

            <Separator />

            <form onSubmit={requestDns} className="space-y-3">
              <div className="space-y-2">
                <Label htmlFor="domain">¿Tienes un dominio propio?</Label>
                <div className="flex gap-2">
                  <Input
                    id="domain"
                    value={domain}
                    onChange={(event) => setDomain(event.target.value)}
                    placeholder="mc.midominio.com"
                  />
                  <Button type="submit" disabled={busy || !domain.trim()}>
                    {busy ? <Loader2 className="animate-spin" /> : null} Ver instrucciones
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  La aplicación no administra tu DNS: sólo te dice qué registros crear en tu
                  proveedor.
                </p>
              </div>

              {records && (
                <ul className="space-y-2">
                  {records.map((record) => (
                    <li key={record.type} className="rounded-lg border border-border p-3 text-sm">
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary">{record.type}</Badge>
                        <code className="truncate font-mono text-xs">{record.name}</code>
                      </div>
                      <div className="mt-2 flex items-center gap-2">
                        <code className="flex-1 truncate rounded bg-muted px-2 py-1 font-mono text-xs">
                          {record.value}
                        </code>
                        <CopyButton value={record.value} />
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">{record.explanation}</p>
                    </li>
                  ))}
                </ul>
              )}
            </form>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function AddressRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="rounded-lg border border-border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <div className="mt-1 flex items-center gap-2">
        <code className="flex-1 truncate font-mono text-sm">{value ?? "no disponible"}</code>
        {value && <CopyButton value={value} />}
      </div>
    </div>
  );
}

function CopyButton({ value }: { value: string }) {
  return (
    <Button
      size="icon-xs"
      variant="ghost"
      aria-label="Copiar"
      onClick={() => {
        void navigator.clipboard.writeText(value);
        toast.success("Copiado.");
      }}
    >
      <Copy />
    </Button>
  );
}
