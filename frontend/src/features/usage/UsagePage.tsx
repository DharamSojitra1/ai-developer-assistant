import { BarChart3 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { errorMessage, isAbortError } from "@/api/errors";
import type { DailyUsage, UsageResponse } from "@/api/types";
import { getMyUsage } from "@/api/usage";
import { TopBar } from "@/components/layout/TopBar";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { Tabs } from "@/components/ui/Tabs";
import { formatCompact, formatNumber } from "@/lib/format";

type Range = "7" | "30" | "90";

function Stat({ label, value, detail }: { label: string; value: number; detail?: string }) {
  return (
    <div className="rounded-panel border border-border bg-surface px-4 py-3.5">
      <dt className="text-xs font-medium text-muted">{label}</dt>
      <dd className="mt-1.5 text-2xl font-semibold tabular-nums tracking-tight" title={formatNumber(value)}>
        {formatCompact(value)}
      </dd>
      {detail && <p className="mt-0.5 text-xs text-subtle">{detail}</p>}
    </div>
  );
}

/** Fills days without usage so the chart has one bar per day, oldest first. */
function fillDays(daily: DailyUsage[], days: number): DailyUsage[] {
  const byDate = new Map(daily.map((day) => [day.date, day]));
  const result: DailyUsage[] = [];
  const today = new Date();

  for (let offset = days - 1; offset >= 0; offset--) {
    const date = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate() - offset));
    const key = date.toISOString().slice(0, 10);
    result.push(
      byDate.get(key) ?? { date: key, requests: 0, llm_calls: 0, input_tokens: 0, output_tokens: 0, total_tokens: 0 },
    );
  }
  return result;
}

function shortDate(isoDate: string): string {
  return new Date(`${isoDate}T00:00:00Z`).toLocaleDateString(undefined, { month: "short", day: "numeric", timeZone: "UTC" });
}

function DailyChart({ days }: { days: DailyUsage[] }) {
  const max = Math.max(1, ...days.map((day) => day.total_tokens));

  return (
    <figure className="rounded-panel border border-border bg-surface px-4 pb-3 pt-4">
      <figcaption className="flex items-center justify-between text-xs">
        <span className="font-medium text-muted">Tokens per day (UTC)</span>
        <span className="flex items-center gap-3 text-subtle">
          <span className="flex items-center gap-1.5">
            <span className="size-2 rounded-sm bg-accent" aria-hidden /> Input
          </span>
          <span className="flex items-center gap-1.5">
            <span className="size-2 rounded-sm bg-accent/45" aria-hidden /> Output
          </span>
        </span>
      </figcaption>
      <div className="mt-4 flex h-40 items-end gap-[3px]" role="img" aria-label="Daily token usage chart. Exact numbers are listed in the table below.">
        {days.map((day) => {
          const inputHeight = (day.input_tokens / max) * 100;
          const outputHeight = (day.output_tokens / max) * 100;
          return (
            <div
              key={day.date}
              className="group relative flex h-full min-w-0 flex-1 flex-col justify-end"
              title={`${shortDate(day.date)}: ${formatNumber(day.total_tokens)} tokens, ${formatNumber(day.requests)} ${day.requests === 1 ? "request" : "requests"}`}
            >
              <div className="rounded-t-[2px] bg-accent/45 transition-opacity group-hover:opacity-80" style={{ height: `${outputHeight}%` }} />
              <div className="bg-accent transition-opacity group-hover:opacity-80" style={{ height: `${inputHeight}%` }} />
              {day.total_tokens === 0 && <div className="h-px bg-border" />}
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex justify-between text-[0.6875rem] text-subtle">
        <span>{shortDate(days[0].date)}</span>
        <span>{shortDate(days[days.length - 1].date)}</span>
      </div>
    </figure>
  );
}

export default function UsagePage() {
  const [range, setRange] = useState<Range>("30");
  const [data, setData] = useState<UsageResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    getMyUsage(Number(range), controller.signal)
      .then(setData)
      .catch((caught) => {
        if (!isAbortError(caught)) setError(errorMessage(caught));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [range, reloadKey]);

  const retry = useCallback(() => setReloadKey((key) => key + 1), []);
  const days = useMemo(() => (data ? fillDays(data.daily, data.days) : []), [data]);
  const activeDays = useMemo(() => [...(data?.daily ?? [])].sort((a, b) => b.date.localeCompare(a.date)), [data]);

  return (
    <>
      <TopBar />
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-4 pb-16 pt-2 sm:px-6 lg:pt-6">
          <header className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">Usage</h1>
              <p className="mt-1.5 text-sm text-muted">Language model tokens used by your requests.</p>
            </div>
            <Tabs
              label="Time range"
              variant="pill"
              value={range}
              onChange={setRange}
              items={[
                { value: "7", label: "7 days" },
                { value: "30", label: "30 days" },
                { value: "90", label: "90 days" },
              ]}
            />
          </header>

          <div className="mt-6" aria-busy={loading}>
            {error ? (
              <ErrorState title="Couldn't load usage" message={error} onRetry={retry} />
            ) : !data ? (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                  {[0, 1, 2, 3].map((key) => (
                    <div key={key} className="skeleton h-[5.5rem] rounded-panel" />
                  ))}
                </div>
                <div className="skeleton h-60 rounded-panel" />
              </div>
            ) : (
              <div className={loading ? "opacity-60 transition-opacity" : "transition-opacity"}>
                <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
                  <Stat label="Total tokens" value={data.totals.total_tokens} />
                  <Stat label="Input tokens" value={data.totals.input_tokens} />
                  <Stat label="Output tokens" value={data.totals.output_tokens} />
                  <Stat label="Requests" value={data.totals.requests} detail={`${formatNumber(data.totals.llm_calls)} model calls`} />
                </dl>

                {data.totals.total_tokens === 0 ? (
                  <EmptyState
                    className="mt-6 rounded-panel border border-dashed border-border"
                    icon={<BarChart3 />}
                    title="No usage in this period"
                    description="Token usage appears here after you chat with the assistant."
                  />
                ) : (
                  <>
                    <div className="mt-6">
                      <DailyChart days={days} />
                    </div>
                    <div className="mt-6 overflow-x-auto rounded-panel border border-border">
                      <table className="w-full text-sm">
                        <caption className="sr-only">Daily usage</caption>
                        <thead className="bg-surface text-left text-xs text-muted">
                          <tr>
                            <th scope="col" className="px-4 py-2.5 font-medium">Date (UTC)</th>
                            <th scope="col" className="px-4 py-2.5 text-right font-medium">Requests</th>
                            <th scope="col" className="px-4 py-2.5 text-right font-medium">Input</th>
                            <th scope="col" className="px-4 py-2.5 text-right font-medium">Output</th>
                            <th scope="col" className="px-4 py-2.5 text-right font-medium">Total</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border tabular-nums">
                          {activeDays.map((day) => (
                            <tr key={day.date}>
                              <td className="px-4 py-2.5">{shortDate(day.date)}</td>
                              <td className="px-4 py-2.5 text-right text-muted">{formatNumber(day.requests)}</td>
                              <td className="px-4 py-2.5 text-right text-muted">{formatNumber(day.input_tokens)}</td>
                              <td className="px-4 py-2.5 text-right text-muted">{formatNumber(day.output_tokens)}</td>
                              <td className="px-4 py-2.5 text-right">{formatNumber(day.total_tokens)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
