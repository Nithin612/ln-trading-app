import { useEffect, useRef } from 'react'
import {
  createChart,
  ColorType,
  CandlestickSeries,
  type IChartApi,
} from 'lightweight-charts'

export interface OhlcvBar {
  time: string   // ISO date string 'YYYY-MM-DD'
  open: number
  high: number
  low: number
  close: number
  volume: number
}

interface Props {
  bars: OhlcvBar[]
  height?: number
}

const CHART_COLORS = {
  bg: '#0e1117',
  grid: '#1e2330',
  text: '#9ca3af',
  upBody: '#22c55e',
  downBody: '#ef4444',
  upWick: '#22c55e',
  downWick: '#ef4444',
}

type AnySeriesApi = ReturnType<IChartApi['addSeries']>

export function CandlestickChart({ bars, height = 340 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<AnySeriesApi | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    chartRef.current = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: CHART_COLORS.bg },
        textColor: CHART_COLORS.text,
      },
      grid: {
        vertLines: { color: CHART_COLORS.grid },
        horzLines: { color: CHART_COLORS.grid },
      },
      width: containerRef.current.clientWidth,
      height,
      timeScale: {
        borderColor: CHART_COLORS.grid,
        timeVisible: false,
      },
      rightPriceScale: {
        borderColor: CHART_COLORS.grid,
      },
    })

    seriesRef.current = chartRef.current.addSeries(CandlestickSeries, {
      upColor: CHART_COLORS.upBody,
      downColor: CHART_COLORS.downBody,
      borderUpColor: CHART_COLORS.upBody,
      borderDownColor: CHART_COLORS.downBody,
      wickUpColor: CHART_COLORS.upWick,
      wickDownColor: CHART_COLORS.downWick,
    })

    const ro = new ResizeObserver((entries) => {
      if (chartRef.current && entries[0]) {
        chartRef.current.applyOptions({ width: entries[0].contentRect.width })
      }
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chartRef.current?.remove()
      chartRef.current = null
      seriesRef.current = null
    }
  }, [height])

  useEffect(() => {
    if (!seriesRef.current || bars.length === 0) return

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const data: any[] = bars.map((b) => ({
      time: b.time.slice(0, 10),
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
    }))

    seriesRef.current.setData(data)
    chartRef.current?.timeScale().fitContent()
  }, [bars])

  if (bars.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-lg border border-(--color-border)"
        style={{ height, background: CHART_COLORS.bg }}
      >
        <span className="text-sm text-(--color-text-muted)">
          No price data available — run bhavcopy ingestion first
        </span>
      </div>
    )
  }

  return <div ref={containerRef} className="rounded-lg overflow-hidden" style={{ height }} />
}
