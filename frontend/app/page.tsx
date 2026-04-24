"use client";

import { Session } from "@supabase/supabase-js";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { signOut } from "@/lib/auth";
import { getSupabaseClient } from "@/lib/supabase";

type RiskStatus = "Normal" | "Warning" | "Critical";
type Scenario = "Stable" | "Gradual Decline" | "Sudden Cardiac Event";
type TrendLabel = "stable" | "declining" | "critical";

type VitalsPoint = {
  hr: number;
  spo2: number;
  movement: number;
  timestamp: string;
  status: RiskStatus;
  scenario: string;
  instant_action?: string | null;
  detailed_steps?: string[];
  trend?: TrendLabel;
};

const MAX_POINTS = 20;
const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/vitals";
const TIMER_RESET_SECONDS = 120;

const scenarios: Scenario[] = ["Stable", "Gradual Decline", "Sudden Cardiac Event"];

const statusStyles: Record<RiskStatus, { label: string; chip: string; card: string }> = {
  Normal: {
    label: "NORMAL",
    chip: "bg-emerald-500 text-emerald-950",
    card: "border-emerald-200 bg-emerald-50",
  },
  Warning: {
    label: "WARNING",
    chip: "bg-amber-400 text-amber-950",
    card: "border-amber-200 bg-amber-50",
  },
  Critical: {
    label: "CRITICAL",
    chip: "bg-red-500 text-red-50",
    card: "border-red-200 bg-red-50",
  },
};

const valueColorMap: Record<RiskStatus, string> = {
  Normal: "text-emerald-600",
  Warning: "text-amber-500",
  Critical: "text-red-600",
};

const trendStyles: Record<TrendLabel, { text: string; className: string }> = {
  stable: { text: "Trend: Stable", className: "text-emerald-600" },
  declining: { text: "Trend: Declining ⚠️", className: "text-amber-500" },
  critical: { text: "Trend: Critical 🚨", className: "text-red-600" },
};

function formatClockLabel(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "--:--:--";
  }

  return date.toLocaleTimeString([], {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function getHeartRateStatus(hr: number): RiskStatus {
  if (hr < 50 || hr > 130) {
    return "Critical";
  }
  if (hr < 60 || hr > 110) {
    return "Warning";
  }
  return "Normal";
}

function getSpo2Status(spo2: number): RiskStatus {
  if (spo2 < 90) {
    return "Critical";
  }
  if (spo2 < 94) {
    return "Warning";
  }
  return "Normal";
}

function formatTimer(seconds: number): string {
  const mins = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const secs = (seconds % 60).toString().padStart(2, "0");
  return `${mins}:${secs}`;
}

export default function Page() {
  const router = useRouter();
  const [points, setPoints] = useState<VitalsPoint[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [scenario, setScenario] = useState<Scenario>("Stable");
  const [timerSeconds, setTimerSeconds] = useState(TIMER_RESET_SECONDS);
  const [timerFlash, setTimerFlash] = useState(false);
  const [authReady, setAuthReady] = useState(false);
  const [userEmail, setUserEmail] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    const setSessionState = (session: Session | null) => {
      if (!mounted) {
        return;
      }

      if (!session) {
        setAuthReady(false);
        setUserEmail(null);
        router.replace("/login");
        return;
      }

      setUserEmail(session.user.email ?? null);
      setAuthReady(true);
    };

    const initialize = async () => {
      try {
        const supabase = getSupabaseClient();
        const {
          data: { session },
        } = await supabase.auth.getSession();
        setSessionState(session);

        const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
          setSessionState(nextSession);
        });

        return () => {
          data.subscription.unsubscribe();
        };
      } catch {
        if (mounted) {
          setAuthReady(false);
          router.replace("/login");
        }
      }

      return undefined;
    };

    let cleanup: (() => void) | undefined;
    void initialize().then((fn) => {
      cleanup = fn;
    });

    return () => {
      mounted = false;
      if (cleanup) {
        cleanup();
      }
    };
  }, [router]);

  useEffect(() => {
    if (!authReady) {
      return;
    }

    setPoints([]);
    const socket = new WebSocket(`${WS_URL}?scenario=${encodeURIComponent(scenario)}`);

    socket.onopen = () => {
      setIsConnected(true);
    };

    socket.onclose = () => {
      setIsConnected(false);
    };

    socket.onerror = () => {
      setIsConnected(false);
    };

    socket.onmessage = (event) => {
      try {
        const incoming = JSON.parse(event.data) as Partial<VitalsPoint>;
        if (
          typeof incoming.hr !== "number" ||
          typeof incoming.spo2 !== "number" ||
          typeof incoming.movement !== "number" ||
          typeof incoming.timestamp !== "string" ||
          typeof incoming.status !== "string" ||
          typeof incoming.scenario !== "string"
        ) {
          return;
        }

        const status =
          incoming.status === "Critical" || incoming.status === "Warning" || incoming.status === "Normal"
            ? incoming.status
            : "Normal";

        const next: VitalsPoint = {
          hr: incoming.hr,
          spo2: incoming.spo2,
          movement: incoming.movement,
          timestamp: incoming.timestamp,
          status,
          scenario: incoming.scenario,
          instant_action:
            typeof incoming.instant_action === "string" || incoming.instant_action === null
              ? incoming.instant_action
              : null,
          detailed_steps:
            Array.isArray(incoming.detailed_steps) && incoming.detailed_steps.every((step) => typeof step === "string")
              ? incoming.detailed_steps
              : [],
          trend:
            incoming.trend === "critical" || incoming.trend === "declining" || incoming.trend === "stable"
              ? incoming.trend
              : "stable",
        };

        setPoints((prev) => {
          const appended = [...prev, next];
          return appended.length > MAX_POINTS ? appended.slice(-MAX_POINTS) : appended;
        });
      } catch {
        // Ignore malformed socket messages.
      }
    };

    return () => {
      socket.close();
    };
  }, [authReady, scenario]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setTimerSeconds((prev) => {
        if (prev <= 1) {
          setTimerFlash(true);
          return TIMER_RESET_SECONDS;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, []);

  useEffect(() => {
    if (!timerFlash) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setTimerFlash(false);
    }, 700);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [timerFlash]);

  const latest = points[points.length - 1];
  const currentStatus: RiskStatus = latest?.status ?? "Normal";
  const currentTrend: TrendLabel = latest?.trend ?? "stable";
  const statusStyle = statusStyles[currentStatus];
  const trendStyle = trendStyles[currentTrend];
  const isCritical = currentStatus === "Critical";

  const hrStatus = latest ? getHeartRateStatus(latest.hr) : "Normal";
  const spo2Status = latest ? getSpo2Status(latest.spo2) : "Normal";

  const chartData = useMemo(
    () =>
      points.map((point) => ({
        ...point,
        timeLabel: formatClockLabel(point.timestamp),
      })),
    [points],
  );

  const handleSignOut = async () => {
    await signOut();
    router.replace("/login");
  };

  if (!authReady) {
    return (
      <main className="min-h-screen bg-slate-100 p-6">
        <div className="mx-auto max-w-md rounded-2xl bg-white p-6 text-sm text-slate-600 shadow-sm ring-1 ring-slate-200">
          Checking session...
        </div>
      </main>
    );
  }

  return (
    <main
      className={`relative min-h-screen p-4 md:p-8 ${
        isCritical ? "bg-red-100" : "bg-slate-100"
      } transition-colors duration-500`}
    >
      {isCritical ? <div className="pointer-events-none absolute inset-0 animate-pulse bg-red-500/10" /> : null}
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="rounded-2xl bg-white px-5 py-4 shadow-sm ring-1 ring-slate-200 md:px-7 md:py-5">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-slate-900 md:text-3xl">REVIVE Monitoring Dashboard</h1>
              <p className="text-sm text-slate-600">Real-time Evaluation of Vitals &amp; Intelligent Virtual Emergency Support</p>
              {userEmail ? <p className="mt-1 text-xs text-slate-500">Signed in: {userEmail}</p> : null}
            </div>
            <div className="flex flex-col gap-2 md:items-end">
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-500" htmlFor="scenario-selector">
                Scenario
              </label>
              <select
                id="scenario-selector"
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 outline-none ring-0 transition focus:border-slate-400"
                value={scenario}
                onChange={(event) => {
                  setScenario(event.target.value as Scenario);
                }}
              >
                {scenarios.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={handleSignOut}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50"
              >
                Sign out
              </button>
            </div>
          </div>
          <div className="mt-4 flex items-center gap-2 self-start rounded-full bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
            <span
              className={`h-2.5 w-2.5 rounded-full ${isConnected ? "bg-emerald-500" : "bg-red-500"}`}
              aria-hidden
            />
            {isConnected ? "LIVE" : "DISCONNECTED"}
          </div>
        </header>

        <section className="grid grid-cols-1 gap-6 rounded-2xl bg-slate-950 p-6 shadow-sm ring-1 ring-slate-800 md:grid-cols-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Current Heart Rate</p>
            <p className={`font-mono text-6xl font-bold tracking-wider ${valueColorMap[hrStatus]}`}>
              {latest?.hr ?? "--"}
              <span className="ml-2 text-xl text-slate-300">BPM</span>
            </p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Current SpO2</p>
            <p className={`font-mono text-6xl font-bold tracking-wider ${valueColorMap[spo2Status]}`}>
              {latest?.spo2 ?? "--"}
              <span className="ml-2 text-xl text-slate-300">%</span>
            </p>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card className="rounded-2xl shadow-sm">
            <CardHeader>
              <CardTitle className="text-sm font-medium uppercase tracking-wide text-slate-500">Heart Rate</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-end gap-2">
                <p className="text-4xl font-bold text-slate-900">{latest?.hr ?? "--"}</p>
                <p className="pb-1 text-sm text-slate-500">BPM</p>
              </div>
              <p className="mt-3 text-xs text-slate-500">Last update: {latest ? formatClockLabel(latest.timestamp) : "Waiting for stream"}</p>
            </CardContent>
          </Card>

          <Card className="rounded-2xl shadow-sm">
            <CardHeader>
              <CardTitle className="text-sm font-medium uppercase tracking-wide text-slate-500">SpO2</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-end gap-2">
                <p className="text-4xl font-bold text-slate-900">{latest?.spo2 ?? "--"}</p>
                <p className="pb-1 text-sm text-slate-500">%</p>
              </div>
              <p className="mt-3 text-xs text-slate-500">Scenario: {latest?.scenario ?? "N/A"}</p>
            </CardContent>
          </Card>

          <Card className={`rounded-2xl border-2 shadow-sm ${statusStyle.card}`}>
            <CardHeader>
              <CardTitle className="text-sm font-medium uppercase tracking-wide text-slate-600">Status</CardTitle>
            </CardHeader>
            <CardContent>
              <div className={`inline-flex rounded-xl px-6 py-3 text-2xl font-extrabold tracking-wide ${statusStyle.chip}`}>
                {statusStyle.label}
              </div>
              <p className={`mt-3 text-sm font-semibold ${trendStyle.className}`}>{trendStyle.text}</p>
              <p className="mt-4 text-sm text-slate-600">Movement: {latest?.movement ?? "--"}</p>
            </CardContent>
          </Card>
        </section>

        <section className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <Card className="rounded-2xl shadow-sm">
            <CardHeader>
              <CardTitle className="text-base font-semibold text-slate-800">Heart Rate Trend</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#cbd5e1" />
                    <XAxis dataKey="timeLabel" tick={{ fontSize: 12, fill: "#475569" }} minTickGap={24} />
                    <YAxis
                      domain={[40, 160]}
                      tick={{ fontSize: 12, fill: "#475569" }}
                      tickCount={7}
                      width={36}
                    />
                    <Tooltip
                      contentStyle={{ borderRadius: 12, borderColor: "#cbd5e1" }}
                      formatter={(value) => [`${value} BPM`, "Heart Rate"]}
                    />
                    <Line
                      type="monotone"
                      dataKey="hr"
                      stroke="#e11d48"
                      strokeWidth={3}
                      dot={false}
                      isAnimationActive
                      animationDuration={350}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          <Card className="rounded-2xl shadow-sm">
            <CardHeader>
              <CardTitle className="text-base font-semibold text-slate-800">SpO2 Trend</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#cbd5e1" />
                    <XAxis dataKey="timeLabel" tick={{ fontSize: 12, fill: "#475569" }} minTickGap={24} />
                    <YAxis
                      domain={[80, 100]}
                      tick={{ fontSize: 12, fill: "#475569" }}
                      tickCount={6}
                      width={36}
                    />
                    <Tooltip
                      contentStyle={{ borderRadius: 12, borderColor: "#cbd5e1" }}
                      formatter={(value) => [`${value}%`, "SpO2"]}
                    />
                    <Line
                      type="monotone"
                      dataKey="spo2"
                      stroke="#0284c7"
                      strokeWidth={3}
                      dot={false}
                      isAnimationActive
                      animationDuration={350}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </section>

        <section className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          <Card className="rounded-2xl border-l-4 border-l-red-500 shadow-sm">
            <CardHeader>
              <CardTitle className="text-base font-semibold text-slate-800">⚡ Instant Action</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm leading-6 text-slate-700">
                {latest?.instant_action && latest.instant_action.trim().length > 0
                  ? latest.instant_action
                  : "No emergency detected"}
              </p>
            </CardContent>
          </Card>

          <Card className="rounded-2xl border-l-4 border-l-blue-500 shadow-sm">
            <CardHeader>
              <CardTitle className="text-base font-semibold text-slate-800">📋 Detailed Guidance</CardTitle>
            </CardHeader>
            <CardContent>
              {latest?.detailed_steps && latest.detailed_steps.length > 0 ? (
                <ol className="list-decimal space-y-1 pl-5 text-sm leading-6 text-slate-700">
                  {latest.detailed_steps.map((step, index) => (
                    <li key={`${step}-${index}`}>{step}</li>
                  ))}
                </ol>
              ) : (
                <p className="text-sm leading-6 text-slate-700">Monitoring patient...</p>
              )}
            </CardContent>
          </Card>

          <Card className={`rounded-2xl shadow-sm transition-colors ${timerFlash ? "bg-amber-100" : "bg-white"}`}>
            <CardHeader>
              <CardTitle className="text-base font-semibold text-slate-800">Golden Hour Support Timer</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="font-mono text-5xl font-bold tracking-widest text-slate-900">{formatTimer(timerSeconds)}</div>
              <p className="mt-3 text-sm text-slate-600">Auto-resets every 2 minutes for patient recheck.</p>
              {timerFlash ? <p className="mt-2 text-sm font-semibold text-amber-700">Recheck patient now.</p> : null}
            </CardContent>
          </Card>
        </section>
      </div>
    </main>
  );
}
