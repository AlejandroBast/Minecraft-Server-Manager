"use client";

import { Coffee, Cpu, HardDrive, MemoryStick, Network } from "lucide-react";
import type { ReactNode } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { formatFrequency, formatGigabytes, formatMemory, formatPercent } from "@/lib/format";
import type { SystemInfo } from "@/lib/types";

interface SystemPanelProps {
  info: SystemInfo | null;
  loading: boolean;
}

export function SystemPanel({ info, loading }: SystemPanelProps) {
  if (loading && !info) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-32 rounded-xl" />
        ))}
      </div>
    );
  }

  if (!info) {
    return null;
  }

  const usedMemoryMb = info.memory.total_mb - info.memory.available_mb;

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard icon={<Cpu />} title="Procesador" value={formatPercent(info.cpu.usage_percent)}>
        <Progress value={info.cpu.usage_percent} />
        <p className="line-clamp-1 text-xs text-muted-foreground" title={info.cpu.name}>
          {info.cpu.physical_cores} núcleos · {info.cpu.logical_cores} hilos ·{" "}
          {formatFrequency(info.cpu.frequency_mhz)}
        </p>
      </MetricCard>

      <MetricCard
        icon={<MemoryStick />}
        title="Memoria"
        value={formatPercent(info.memory.used_percent)}
      >
        <Progress value={info.memory.used_percent} />
        <p className="text-xs text-muted-foreground">
          {formatMemory(usedMemoryMb)} de {formatMemory(info.memory.total_mb)} en uso
        </p>
      </MetricCard>

      <MetricCard
        icon={<HardDrive />}
        title="Disco"
        value={formatGigabytes(info.disk.free_gb)}
        valueLabel="libres"
      >
        <Progress value={info.disk.used_percent} />
        <p className="line-clamp-1 text-xs text-muted-foreground" title={info.disk.path}>
          {formatGigabytes(info.disk.total_gb)} en total
        </p>
      </MetricCard>

      <MetricCard icon={<Network />} title="Red" value={info.network.local_ip} valueClassName="text-lg">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="outline">{info.network.hostname}</Badge>
          <Badge variant="secondary">
            {info.network.public_ip ?? "IP pública en la fase 9"}
          </Badge>
        </div>
        <Button
          variant="ghost"
          size="xs"
          onClick={() => {
            void navigator.clipboard.writeText(info.network.local_ip);
            toast.success("IP local copiada.");
          }}
        >
          Copiar IP
        </Button>
      </MetricCard>

      <Card className="sm:col-span-2 xl:col-span-4">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <Coffee className="size-4" /> Java y sistema
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-2 text-sm">
          {info.java.installed ? (
            <>
              <Badge variant="secondary">Java {info.java.major}</Badge>
              <span className="text-muted-foreground">
                {info.java.version}
                {info.java.managed ? " · gestionado por la aplicación" : " · instalado en el sistema"}
              </span>
            </>
          ) : (
            <Badge variant="outline">Sin Java detectado</Badge>
          )}
          {info.java.installed && info.java.major !== null && info.java.major < 17 && (
            <span className="text-xs text-amber-600 dark:text-amber-400">
              Las versiones modernas de Minecraft necesitan Java 17 o superior: la aplicación lo
              descargará automáticamente.
            </span>
          )}
          <span className="ml-auto text-xs text-muted-foreground">
            {info.os} {info.architecture}
          </span>
        </CardContent>
      </Card>
    </div>
  );
}

interface MetricCardProps {
  icon: ReactNode;
  title: string;
  value: string;
  valueLabel?: string;
  valueClassName?: string;
  children: ReactNode;
}

function MetricCard({
  icon,
  title,
  value,
  valueLabel,
  valueClassName = "text-2xl",
  children,
}: MetricCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <span className="[&_svg]:size-4">{icon}</span>
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className={`font-semibold tabular-nums ${valueClassName}`}>
          {value}
          {valueLabel && (
            <span className="ml-1 text-xs font-normal text-muted-foreground">{valueLabel}</span>
          )}
        </p>
        {children}
      </CardContent>
    </Card>
  );
}
