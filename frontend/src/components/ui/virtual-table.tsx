/**
 * Virtual-table building blocks (Phase 5) — pair these with `useVirtualRows`.
 *
 *   const viewportRef = useRef<HTMLDivElement>(null)
 *   const win = useVirtualRows(viewportRef, { count: rows.length, rowHeight: 36 })
 *   ...
 *   <VirtualViewport ref={viewportRef} className="max-h-[70vh]">
 *     <Table>
 *       <TableHeader>…</TableHeader>
 *       <TableBody>
 *         <VirtualSpacer height={win.padTop} colSpan={9} />
 *         {rows.slice(win.startIndex, win.endIndex).map(…)}
 *         <VirtualSpacer height={win.padBottom} colSpan={9} />
 *       </TableBody>
 *     </Table>
 *   </VirtualViewport>
 *
 * The spacers stand in for the un-rendered rows so the scrollbar keeps the
 * geometry of the full dataset.
 */

import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * A bounded, scrolling container — the scroll parent that `useVirtualRows`
 * measures and that the sticky table header sticks to. Give it a height bound
 * (`max-h-*`/`h-*`) or nothing will ever scroll.
 *
 * The `[&_[data-slot=table-container]]:overflow-visible` override is load
 * bearing, not tidying. `Table` wraps itself in `overflow-x-auto`, and CSS
 * promotes the other axis to `auto` too — so that wrapper becomes a scroll
 * container and therefore the containing block for `position: sticky`. Because
 * it is unbounded it never actually scrolls, so the sticky `<thead>` inside it
 * simply travels with the content: measured in Chrome, scrolling this viewport
 * 800 px moved the header to `top: -761` — i.e. straight off screen, losing the
 * column headers on exactly the long tables that need them. Neutralising the
 * inner wrapper makes THIS element the sticky ancestor. Horizontal scrolling
 * moves here too (`overflow-auto`), so wide tables still scroll sideways.
 */
const VirtualViewport = React.forwardRef<HTMLDivElement, React.ComponentProps<"div">>(
  function VirtualViewport({ className, ...props }, ref) {
    return (
      <div
        ref={ref}
        data-slot="virtual-viewport"
        className={cn(
          "overflow-auto overscroll-contain",
          "[&_[data-slot=table-container]]:overflow-visible",
          className,
        )}
        {...props}
      />
    )
  },
)

interface VirtualSpacerProps {
  /** Pixel height to reserve; <= 0 renders nothing. */
  height: number
  /** Must span every column so the spacer can't disturb column widths. */
  colSpan: number
}

/**
 * Filler row representing the rows outside the rendered window. Hidden from
 * assistive tech — it carries no data, only geometry.
 */
function VirtualSpacer({ height, colSpan }: VirtualSpacerProps) {
  if (height <= 0) return null
  return (
    <tr aria-hidden="true" data-slot="virtual-spacer" style={{ height }}>
      <td colSpan={colSpan} className="p-0 border-0" />
    </tr>
  )
}

export { VirtualViewport, VirtualSpacer }
