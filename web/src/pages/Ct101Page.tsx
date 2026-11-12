import { useEffect, useState } from "react";
import {
  Activity, Brain, Cpu, Database, Server,
  TrendingUp, Zap, Check, X, BarChart3, Code, Layers,
} from "lucide-react";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { H2 } from "@nous-research/ui/ui/components/typography/h2";
import { Card, CardContent } from "@nous-research/ui/ui/components/card";
import { cn } from "@/lib/utils";
import { fetchJSON } from "@/lib/api";

interface Ct101Overview {
  ct101_root: string;
  openssl_preloaded: boolean;
  domain: { packages: number; total_classes: number; total_functions: number };
  cpp_bridge: {
    ready: boolean;
    modules: string[];
    total_functions: number;
    total_classes: number;
    indicator_count: number;
    errors: Record<string, string>;
  };
  bots: {
    loaded: number;
    names: string[];
    total_available: number;
    errors: Record<string, string>;
  };
}

function StatCard({ icon: Icon, label, value, subtitle }: {
  icon: React.ComponentType<{ className?: string }>;
  label: string; value: string | number; subtitle?: string;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-3">
          <Icon className="h-5 w-5 text-muted-foreground" />
          <div>
            <div className="text-2xl font-bold">{value}</div>
            <div className="text-sm text-muted-foreground">{label}</div>
            {subtitle && <div className="text-xs text-muted-foreground mt-1">{subtitle}</div>}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function Ct101Page() {
  const [data, setData] = useState<Ct101Overview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJSON<Ct101Overview>("/api/ct101/overview")
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="p-6">
        <H2>CT101</H2>
        <Card className="mt-4 border-destructive/50">
          <CardContent className="p-6">
            <div className="flex items-center gap-2 text-destructive">
              <X className="h-5 w-5" />
              <span>CT101 integration unavailable: {error}</span>
            </div>
            <p className="text-sm text-muted-foreground mt-2">
              The CT101 Python module (hermes_agent.ct101) must be importable
              on the gateway host with all dependencies installed.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex min-h-[12rem] flex-1 items-center justify-center" aria-busy="true">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner />
          <span>Loading CT101 status…</span>
        </div>
      </div>
    );
  }

  const { domain, cpp_bridge, bots } = data;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <TrendingUp className="h-6 w-6" />
        <H2>CT101 Trading System</H2>
        {cpp_bridge.ready
          ? <Badge variant="default"><Check className="h-3 w-3 mr-1" />Connected</Badge>
          : <Badge variant="destructive"><X className="h-3 w-3 mr-1" />C++ Bridge Offline</Badge>
        }
      </div>

      {/* Domain */}
      <div>
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Code className="h-4 w-4" /> Domain
        </h3>
        <div className="grid grid-cols-3 gap-3">
          <StatCard icon={Layers} label="Packages" value={domain.packages} />
          <StatCard icon={Code} label="Classes" value={domain.total_classes} />
          <StatCard icon={Activity} label="Functions" value={domain.total_functions} />
        </div>
      </div>

      {/* C++ Bridge */}
      <div>
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Cpu className="h-4 w-4" /> C++ Bridge
        </h3>
        <div className="grid grid-cols-4 gap-3">
          <StatCard icon={Zap} label="Ready" value={cpp_bridge.ready ? "Yes" : "No"} />
          <StatCard icon={Cpu} label="Functions" value={cpp_bridge.total_functions} />
          <StatCard icon={Database} label="Classes" value={cpp_bridge.total_classes} />
          <StatCard icon={BarChart3} label="TA-Lib Indicators" value={cpp_bridge.indicator_count}
            subtitle={cpp_bridge.modules.join(", ")} />
        </div>
        {Object.keys(cpp_bridge.errors).length > 0 && (
          <Card className="mt-3 border-yellow-500/50">
            <CardContent className="p-3">
              <div className="text-sm text-yellow-600 dark:text-yellow-400">
                {Object.entries(cpp_bridge.errors).map(([k, v]) => (
                  <div key={k}>{k}: {v}</div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Bots */}
      <div>
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Brain className="h-4 w-4" /> Bot Fleet
        </h3>
        <div className="grid grid-cols-2 gap-3">
          <StatCard icon={Brain} label="Bots Loaded" value={`${bots.loaded}/${bots.total_available}`} />
          <StatCard icon={Server} label="Names" value={bots.names.length > 0 ? bots.names.join(", ") : "None"}
            subtitle={Object.keys(bots.errors).length > 0
              ? Object.entries(bots.errors).map(([k, v]) => `${k}: ${v}`).join("; ")
              : undefined} />
        </div>
      </div>

      {/* Root */}
      <div className="text-xs text-muted-foreground">
        CT101 root: {data.ct101_root} · OpenSSL preloaded: {data.openssl_preloaded ? "Yes" : "No"}
      </div>
    </div>
  );
}