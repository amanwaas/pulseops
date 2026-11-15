import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import * as echarts from 'echarts';
import { LatencyAndTimelineResponse } from '../api/types';
import { Activity, Clock, Zap, AlertTriangle } from 'lucide-react';
import { format, parseISO } from 'date-fns';

interface LatencyTimelineChartProps {
  data: LatencyAndTimelineResponse | undefined;
  isLoading: boolean;
  selectedWindow: '1h' | '24h' | '7d';
  onWindowChange: (w: '1h' | '24h' | '7d') => void;
}

export const LatencyTimelineChart: React.FC<LatencyTimelineChartProps> = ({
  data,
  isLoading,
  selectedWindow,
  onWindowChange,
}) => {
  const chartOption = useMemo(() => {
    if (!data || !data.points || data.points.length === 0) {
      return null;
    }

    const timestamps = data.points.map((p) => {
      try {
        return format(parseISO(p.timestamp), selectedWindow === '1h' ? 'HH:mm:ss' : 'MMM dd HH:mm');
      } catch {
        return p.timestamp;
      }
    });

    const latencyValues = data.points.map((p) => p.latency_ms);

    // Build deployment markLines / markPoints overlaid at exact timestamp
    const deploymentMarks = data.deployments.map((d) => {
      const depDateFormatted = format(
        parseISO(d.timestamp),
        selectedWindow === '1h' ? 'HH:mm:ss' : 'MMM dd HH:mm'
      );

      const isSuccess = d.status === 'success';
      const markColor = isSuccess ? '#10b981' : '#f43f5e';

      return {
        name: `Deploy: ${d.short_sha}`,
        xAxis: depDateFormatted,
        value: `${d.short_sha} (${d.status})`,
        itemStyle: {
          color: markColor,
        },
        label: {
          formatter: `🚀 ${d.short_sha}`,
          position: 'insideEndTop',
          color: '#e2e8f0',
          backgroundColor: isSuccess ? 'rgba(6, 78, 59, 0.9)' : 'rgba(136, 19, 55, 0.9)',
          borderColor: markColor,
          borderWidth: 1,
          borderRadius: 4,
          padding: [3, 6],
          fontSize: 10,
          fontFamily: 'monospace',
        },
      };
    });

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#0f172a',
        borderColor: '#334155',
        borderWidth: 1,
        textStyle: { color: '#f8fafc', fontSize: 12 },
        formatter: (params: any) => {
          if (!params || !params[0]) return '';
          const p = params[0];
          const pointIndex = p.dataIndex;
          const originalPoint = data.points[pointIndex];
          const timeStr = originalPoint?.timestamp
            ? format(parseISO(originalPoint.timestamp), 'yyyy-MM-dd HH:mm:ss')
            : p.name;

          let html = `
            <div style="font-family: Inter, sans-serif; min-width: 180px;">
              <div style="color: #94a3b8; font-size: 11px; margin-bottom: 4px;">${timeStr}</div>
              <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 4px;">
                <span style="color: #cbd5e1;">Latency:</span>
                <span style="font-family: monospace; font-weight: 700; color: #818cf8;">${p.value} ms</span>
              </div>
              <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px;">
                <span style="color: #cbd5e1;">Status:</span>
                <span style="font-family: monospace; color: ${originalPoint?.is_up ? '#34d399' : '#f87171'};">
                  ${originalPoint?.status_code || (originalPoint?.is_up ? '200 OK' : 'FAILED')}
                </span>
              </div>
          `;

          // Check if any deployment correlates with this time
          const matchingDeployments = data.deployments.filter((d) => {
            const diffMs = Math.abs(new Date(d.timestamp).getTime() - new Date(originalPoint.timestamp).getTime());
            return diffMs < 1000 * 60 * 30; // Within 30 minutes
          });

          if (matchingDeployments.length > 0) {
            html += `<div style="margin-top: 6px; padding-top: 6px; border-top: 1px solid #1e293b;">`;
            matchingDeployments.forEach((d) => {
              html += `
                <div style="font-size: 11px; color: #a5b4fc; font-weight: 600;">
                  🚀 Deployment: ${d.short_sha} (${d.status.toUpperCase()})
                </div>
                <div style="font-size: 10px; color: #94a3b8;">Author: ${d.author || 'CI'} • Env: ${d.environment}</div>
              `;
            });
            html += `</div>`;
          }

          html += `</div>`;
          return html;
        },
      },
      grid: {
        left: '2%',
        right: '3%',
        top: '12%',
        bottom: '8%',
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        data: timestamps,
        boundaryGap: false,
        axisLine: { lineStyle: { color: '#334155' } },
        axisLabel: { color: '#94a3b8', fontSize: 11 },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value',
        name: 'Latency (ms)',
        nameTextStyle: { color: '#64748b', fontSize: 11 },
        splitLine: { lineStyle: { color: '#1e293b', type: 'dashed' } },
        axisLabel: { color: '#94a3b8', fontSize: 11 },
      },
      series: [
        {
          name: 'Latency',
          type: 'line',
          smooth: true,
          showSymbol: false,
          data: latencyValues,
          lineStyle: {
            color: '#6366f1',
            width: 2.5,
          },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(99, 102, 241, 0.35)' },
              { offset: 1, color: 'rgba(99, 102, 241, 0.01)' },
            ]),
          },
          markLine: {
            symbol: ['none', 'none'],
            data: deploymentMarks.map((m) => ({
              xAxis: m.xAxis,
              lineStyle: {
                color: m.itemStyle.color,
                type: 'dashed',
                width: 1.5,
              },
              label: m.label,
            })),
          },
        },
      ],
    };
  }, [data, selectedWindow]);

  if (isLoading) {
    return (
      <div className="h-72 rounded-2xl border border-surface-800 bg-surface-900/40 flex items-center justify-center text-slate-500 font-mono text-xs">
        Loading latency telemetry & deployment markers...
      </div>
    );
  }

  if (!data || data.points.length === 0) {
    return (
      <div className="h-72 rounded-2xl border border-surface-800 bg-surface-900/40 flex flex-col items-center justify-center text-slate-500 gap-2">
        <Activity className="w-8 h-8 text-slate-600" />
        <span className="text-sm">No health telemetry data recorded for this window.</span>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-surface-800 bg-surface-900/40 p-5 shadow-sm">
      {/* Chart Header: Metric Pills & Window Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
        {/* Metric Badges */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-surface-950/80 border border-surface-800 text-xs">
            <span className="text-slate-400">Uptime:</span>
            <span className={`font-mono font-bold ${data.uptime_percentage >= 99 ? 'text-emerald-400' : 'text-amber-400'}`}>
              {data.uptime_percentage}%
            </span>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-surface-950/80 border border-surface-800 text-xs">
            <span className="text-slate-400">Avg Latency:</span>
            <span className="font-mono font-bold text-slate-200">
              {data.avg_latency_ms} <span className="font-normal text-slate-500">ms</span>
            </span>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-surface-950/80 border border-surface-800 text-xs">
            <span className="text-slate-400">p95 Latency:</span>
            <span className={`font-mono font-bold ${data.p95_latency_ms > 500 ? 'text-amber-400' : 'text-emerald-400'}`}>
              {data.p95_latency_ms} <span className="font-normal text-slate-500">ms</span>
            </span>
          </div>

          {data.deployments.length > 0 && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-brand-950/60 border border-brand-500/30 text-xs text-brand-300">
              <span>🚀</span>
              <span className="font-semibold">{data.deployments.length}</span>
              <span className="text-brand-400/80">Releases Overlaid</span>
            </div>
          )}
        </div>

        {/* Time Window Selector */}
        <div className="flex items-center gap-1 p-1 rounded-xl bg-surface-950/80 border border-surface-800 self-start sm:self-auto">
          {(['1h', '24h', '7d'] as const).map((w) => (
            <button
              key={w}
              onClick={() => onWindowChange(w)}
              className={`px-3 py-1 rounded-lg text-xs font-mono font-medium transition-colors ${
                selectedWindow === w
                  ? 'bg-brand-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-surface-800'
              }`}
            >
              {w}
            </button>
          ))}
        </div>
      </div>

      {/* Interactive ECharts Surface */}
      <div className="w-full h-72">
        {chartOption && (
          <ReactECharts
            option={chartOption}
            style={{ height: '100%', width: '100%' }}
            notMerge={true}
            lazyUpdate={true}
          />
        )}
      </div>
    </div>
  );
};
