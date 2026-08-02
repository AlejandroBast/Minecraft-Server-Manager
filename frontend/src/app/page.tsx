"use client";

import { Boxes, Globe, RefreshCw, ServerOff } from "lucide-react";
import { useState } from "react";

import { CreateServerDialog } from "@/components/create-server-dialog";
import { NetworkDialog } from "@/components/network-dialog";
import { ServerCard } from "@/components/server-card";
import { SystemPanel } from "@/components/system-panel";
import { ThemeToggle } from "@/components/theme-toggle";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { usePolling } from "@/hooks/use-polling";
import { API_URL, NetworkError, api } from "@/lib/api";

const SERVERS_INTERVAL_MS = 5000;
const SYSTEM_INTERVAL_MS = 5000;
const RECOMMENDATIONS_INTERVAL_MS = 30000;

export default function DashboardPage() {
  const [networkOpen, setNetworkOpen] = useState(false);
  const servers = usePolling(api.listServers, SERVERS_INTERVAL_MS);
  const system = usePolling(api.systemInfo, SYSTEM_INTERVAL_MS);
  const recommendations = usePolling(api.recommendations, RECOMMENDATIONS_INTERVAL_MS);

  const offline = servers.error instanceof NetworkError || system.error instanceof NetworkError;

  function refreshAll() {
    void servers.refresh();
    void system.refresh();
    void recommendations.refresh();
  }

  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-10">
      <header className="mb-10 flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">Minecraft Server Manager</h1>
          <p className="text-sm text-muted-foreground">
            Crea y administra servidores desde tu propio equipo.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" aria-label="Actualizar" onClick={refreshAll}>
            <RefreshCw />
          </Button>
          <Button variant="outline" onClick={() => setNetworkOpen(true)}>
            <Globe /> Red
          </Button>
          <ThemeToggle />
          <CreateServerDialog recommendations={recommendations.data ?? []} onCreated={refreshAll} />
        </div>
      </header>

      {offline ? (
        <Alert variant="destructive">
          <ServerOff />
          <AlertTitle>No se puede conectar con el backend</AlertTitle>
          <AlertDescription>
            <p>
              No hay respuesta en <code className="font-mono">{API_URL}</code>. Arranca la API con{" "}
              <code className="font-mono">python run.py</code> dentro de la carpeta{" "}
              <code className="font-mono">backend</code>.
            </p>
          </AlertDescription>
        </Alert>
      ) : (
        <div className="space-y-10">
          <section className="space-y-4">
            <h2 className="text-sm font-medium text-muted-foreground">Tu equipo</h2>
            <SystemPanel info={system.data} loading={system.loading} />
          </section>

          <section className="space-y-4">
            <h2 className="text-sm font-medium text-muted-foreground">
              Servidores{" "}
              {servers.data && servers.data.length > 0 && (
                <span className="tabular-nums">({servers.data.length})</span>
              )}
            </h2>

            {servers.loading && !servers.data ? (
              <div className="grid gap-4 md:grid-cols-2">
                <Skeleton className="h-64 rounded-xl" />
                <Skeleton className="h-64 rounded-xl" />
              </div>
            ) : servers.data && servers.data.length > 0 ? (
              <div className="grid gap-4 md:grid-cols-2">
                {servers.data.map((server) => (
                  <ServerCard key={server.id} server={server} onChanged={refreshAll} />
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-border py-16 text-center">
                <Boxes className="size-8 text-muted-foreground" />
                <div className="space-y-1">
                  <p className="font-medium">Todavía no hay servidores</p>
                  <p className="text-sm text-muted-foreground">
                    Crea el primero: el programa se encarga de Java y de los archivos.
                  </p>
                </div>
                <CreateServerDialog
                  recommendations={recommendations.data ?? []}
                  onCreated={refreshAll}
                />
              </div>
            )}
          </section>
        </div>
      )}

      {networkOpen && <NetworkDialog open={networkOpen} onOpenChange={setNetworkOpen} />}
    </main>
  );
}
