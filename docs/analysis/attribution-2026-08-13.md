# Entry-quality attribution — 2026-08-13

_Terminal signal outcomes since 2026-07-19. Read-only. Expectancy_r = mean over decided of (+RR / −1R), winsorized at ±10R (tiny-SL artifacts). reach1R (MFE ≥ +1R), mfe & mae are over `meas` rows (excursion computed), not n. Cells with n < 20 are shown but **not ranked** (†).__

## Tradeable cohort — n=206

### Confidence
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 80–89 | 44 | 41 | 44 | 23% | 34% | +1.09 | -0.89 | -0.01 |
| 70–79 | 148 | 133 | 146 | 41% | 27% | +0.85 | -0.71 | -0.01 |
| 90–100 † | 6 | 6 | 6 | 50% | 17% | +0.74 | -0.36 | +0.64 |
| <70 (sub-gate) † | 8 | 8 | 8 | 50% | 38% | +1.14 | -0.73 | -0.03 |

### Regime (ADX)
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| trending (ADX≥25) | 43 | 39 | 41 | 52% | 41% | +1.02 | -0.90 | +0.38 |
| transitional (20–25) | 96 | 88 | 96 | 36% | 26% | +0.96 | -0.64 | -0.04 |
| choppy (ADX<20) | 67 | 61 | 67 | 28% | 24% | +0.77 | -0.78 | -0.21 |

### Direction
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| BUY | 133 | 126 | 131 | 36% | 34% | +1.12 | -0.80 | +0.04 |
| SELL | 73 | 62 | 73 | 43% | 19% | +0.52 | -0.62 | -0.12 |

### Setup
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| (base) | 175 | 159 | 173 | 41% | 30% | +0.95 | -0.73 | +0.05 |
| multibagger † | 14 | 14 | 14 | 21% | 36% | +1.26 | -0.93 | -0.14 |
| dc2 † | 6 | 5 | 6 | 0% | 0% | +0.14 | -0.80 | -1.00 |
| dc1 † | 7 | 6 | 7 | — | 14% | +0.25 | -0.66 | — |
| rrbo_basic † | 2 | 2 | 2 | — | 0% | +0.09 | -0.51 | — |
| rrbo_trailing † | 2 | 2 | 2 | — | 0% | +0.09 | -0.51 | — |

### Time of day
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| eod (1d) | 206 | 188 | 204 | 37% | 28% | +0.91 | -0.74 | +0.01 |

### Confidence × Regime
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 70–79 · trending (ADX≥25) | 27 | 23 | 25 | 57% | 44% | +0.99 | -1.05 | +0.52 |
| 70–79 · choppy (ADX<20) | 39 | 35 | 39 | 40% | 21% | +0.77 | -0.62 | +0.10 |
| 70–79 · transitional (20–25) | 82 | 75 | 82 | 34% | 24% | +0.84 | -0.65 | -0.30 |
| 80–89 · choppy (ADX<20) | 24 | 22 | 24 | 0% | 29% | +0.77 | -1.12 | -1.00 |
| 90–100 · choppy (ADX<20) † | 4 | 4 | 4 | 100% | 25% | +0.83 | -0.30 | +2.29 |
| 80–89 · transitional (20–25) † | 12 | 11 | 12 | 50% | 42% | +1.80 | -0.61 | +1.55 |
| 80–89 · trending (ADX≥25) † | 8 | 8 | 8 | 40% | 38% | +0.98 | -0.62 | +0.31 |
| <70 (sub-gate) · trending (ADX≥25) † | 8 | 8 | 8 | 50% | 38% | +1.14 | -0.73 | -0.03 |
| 90–100 · transitional (20–25) † | 2 | 2 | 2 | 0% | 0% | +0.57 | -0.47 | -1.00 |

### Factor · ADX
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| supportive | 43 | 39 | 41 | 52% | 41% | +1.02 | -0.90 | +0.38 |
| neutral | 163 | 149 | 163 | 32% | 25% | +0.88 | -0.70 | -0.11 |

### Factor · BEARISH_ENGULFING
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| supportive | 47 | 42 | 47 | 50% | 19% | +0.54 | -0.53 | +0.02 |
| neutral | 159 | 146 | 157 | 36% | 31% | +1.02 | -0.80 | +0.01 |

### Factor · BULLISH_ENGULFING
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| neutral | 153 | 137 | 151 | 35% | 26% | +0.92 | -0.70 | +0.03 |
| supportive | 53 | 51 | 53 | 42% | 36% | +0.89 | -0.85 | -0.05 |

### Factor · FII_DII_FLOW
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| neutral | 148 | 131 | 146 | 41% | 27% | +0.89 | -0.75 | +0.08 |
| supportive | 52 | 51 | 52 | 32% | 29% | +0.95 | -0.69 | -0.07 |
| against † | 6 | 6 | 6 | 20% | 50% | +1.12 | -0.75 | -0.59 |

### Factor · MACD_CROSS
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| neutral | 163 | 149 | 161 | 36% | 30% | +0.97 | -0.73 | +0.06 |
| supportive | 43 | 39 | 43 | 40% | 23% | +0.67 | -0.76 | -0.19 |

### Factor · MACD_HISTOGRAM
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| neutral | 173 | 160 | 173 | 39% | 26% | +0.89 | -0.69 | +0.06 |
| supportive | 33 | 28 | 31 | 29% | 42% | +1.00 | -1.00 | -0.30 |

### Factor · MORNING_STAR
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| supportive | 22 | 19 | 20 | 45% | 35% | +1.16 | -0.61 | +0.05 |
| neutral | 184 | 169 | 184 | 36% | 28% | +0.88 | -0.75 | +0.00 |

### Factor · MULTIBAGGER_EMA
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| neutral | 177 | 159 | 175 | 45% | 26% | +0.84 | -0.70 | +0.16 |
| supportive | 29 | 29 | 29 | 21% | 41% | +1.31 | -0.96 | -0.34 |

### Factor · PRICE_VS_EMA
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| neutral | 176 | 161 | 174 | 35% | 30% | +0.93 | -0.76 | +0.02 |
| supportive | 30 | 27 | 30 | 50% | 20% | +0.80 | -0.60 | -0.05 |

### Factor · RSI_LEVEL
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| neutral | 178 | 164 | 176 | 37% | 26% | +0.86 | -0.74 | +0.02 |
| supportive | 28 | 24 | 28 | 36% | 43% | +1.21 | -0.73 | -0.11 |

### Factor · SR_ZONE
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| supportive | 158 | 142 | 156 | 43% | 28% | +0.80 | -0.66 | +0.01 |
| neutral | 48 | 46 | 48 | 22% | 31% | +1.25 | -1.00 | +0.00 |

### Factor · VOLUME
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| supportive | 46 | 42 | 46 | 48% | 20% | +0.70 | -0.59 | +0.09 |
| neutral | 160 | 146 | 158 | 33% | 31% | +0.97 | -0.78 | -0.03 |

## Shadow cohort — n=19

### Confidence
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| <70 (sub-gate) † | 2 | 2 | 2 | 100% | 100% | +2.09 | +0.09 | +2.00 |
| 80–89 † | 4 | 4 | 4 | 50% | 25% | +0.86 | -0.76 | +0.50 |
| 70–79 † | 13 | 13 | 13 | 29% | 54% | +0.88 | -0.50 | -0.29 |

### Regime (ADX)
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| choppy (ADX<20) † | 6 | 6 | 6 | 50% | 33% | +0.85 | -0.70 | +0.50 |
| trending (ADX≥25) † | 8 | 8 | 8 | 50% | 62% | +1.21 | -0.35 | +0.42 |
| transitional (20–25) † | 5 | 5 | 5 | 33% | 60% | +0.84 | -0.46 | -0.17 |

### Direction
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| SELL † | 6 | 6 | 6 | 100% | 50% | +0.89 | -0.22 | +1.50 |
| BUY † | 13 | 13 | 13 | 40% | 54% | +1.05 | -0.61 | +0.15 |

### Setup
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| pdh_pdl † | 4 | 4 | 4 | 50% | 50% | +1.12 | -0.52 | +0.50 |
| gainer_925 † | 4 | 4 | 4 | 50% | 75% | +1.05 | -0.11 | +0.25 |
| orb_15m † | 11 | 11 | 11 | 40% | 45% | +0.94 | -0.62 | +0.20 |

### Time of day
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 13:00–13:59 IST † | 1 | 1 | 1 | 100% | 100% | +2.02 | -0.04 | +2.00 |
| 09:00–09:59 IST † | 4 | 4 | 4 | 50% | 75% | +1.05 | -0.11 | +0.25 |
| 14:00–14:59 IST † | 7 | 7 | 7 | 40% | 57% | +1.16 | -0.60 | +0.20 |
| 12:00–12:59 IST † | 5 | 5 | 5 | 0% | 20% | +0.62 | -0.83 | -1.00 |
| 15:00–15:59 IST † | 2 | 2 | 2 | — | 50% | +0.80 | -0.25 | — |

### Confidence × Regime
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| <70 (sub-gate) · trending (ADX≥25) † | 2 | 2 | 2 | 100% | 100% | +2.09 | +0.09 | +2.00 |
| 80–89 · choppy (ADX<20) † | 4 | 4 | 4 | 50% | 25% | +0.86 | -0.76 | +0.50 |
| 70–79 · transitional (20–25) † | 5 | 5 | 5 | 33% | 60% | +0.84 | -0.46 | -0.17 |
| 70–79 · trending (ADX≥25) † | 6 | 6 | 6 | 25% | 50% | +0.92 | -0.50 | -0.38 |
| 70–79 · choppy (ADX<20) † | 2 | 2 | 2 | — | 50% | +0.84 | -0.59 | — |

† n < 20 — shown for completeness, not ranked (insufficient sample).