export function seededSpark(id: number): number[] {
  let x = id * 9301 + 49297
  const out: number[] = []
  for (let i = 0; i < 7; i++) {
    x = (x * 9301 + 49297) % 233280
    out.push(100 + (x / 233280) * 20 - 10)
  }
  return out
}
