# Entry-quality attribution — 2026-08-13

_Terminal signal outcomes since 2023-09-13. Read-only. Expectancy_r = mean over decided of (+RR / −1R), winsorized at ±10R (tiny-SL artifacts). reach1R (MFE ≥ +1R), mfe & mae are over `meas` rows (excursion computed), not n. Cells with n < 20 are shown but **not ranked** (†).__

## Corpus cohort — n=816

### Confidence
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 80–89 | 307 | 307 | 307 | 43% | 48% | +1.53 | -1.29 | +0.20 |
| 90–100 | 62 | 62 | 62 | 43% | 40% | +1.24 | -0.94 | +0.11 |
| 70–79 | 434 | 434 | 434 | 37% | 42% | +1.12 | -1.16 | -0.07 |
| <70 (sub-gate) † | 13 | 13 | 13 | 46% | 54% | +1.16 | -0.84 | +0.13 |

### Regime (ADX)
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| trending (ADX≥25) | 140 | 140 | 140 | 46% | 45% | +1.22 | -0.86 | +0.24 |
| choppy (ADX<20) | 337 | 337 | 337 | 41% | 46% | +1.45 | -1.27 | +0.12 |
| transitional (20–25) | 339 | 339 | 339 | 36% | 42% | +1.14 | -1.24 | -0.10 |

### Direction
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| BUY | 434 | 434 | 434 | 40% | 46% | +1.35 | -1.22 | +0.09 |
| SELL | 382 | 382 | 382 | 40% | 42% | +1.21 | -1.14 | +0.01 |

### Setup
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| (corpus base) | 816 | 816 | 816 | 40% | 44% | +1.28 | -1.18 | +0.05 |

### Time of day
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| eod (1d) | 816 | 816 | 816 | 40% | 44% | +1.28 | -1.18 | +0.05 |

### Confidence × Regime
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 80–89 · transitional (20–25) | 75 | 75 | 75 | 49% | 57% | +1.55 | -1.16 | +0.32 |
| 70–79 · trending (ADX≥25) | 75 | 75 | 75 | 48% | 48% | +1.24 | -0.89 | +0.27 |
| 80–89 · trending (ADX≥25) | 52 | 52 | 52 | 44% | 38% | +1.20 | -0.81 | +0.22 |
| 90–100 · choppy (ADX<20) | 48 | 48 | 48 | 46% | 44% | +1.34 | -0.93 | +0.20 |
| 80–89 · choppy (ADX<20) | 180 | 180 | 180 | 40% | 46% | +1.61 | -1.48 | +0.14 |
| 70–79 · choppy (ADX<20) | 109 | 109 | 109 | 42% | 48% | +1.24 | -1.06 | +0.06 |
| 70–79 · transitional (20–25) | 250 | 250 | 250 | 32% | 38% | +1.03 | -1.27 | -0.23 |
| <70 (sub-gate) · trending (ADX≥25) † | 13 | 13 | 13 | 46% | 54% | +1.16 | -0.84 | +0.13 |
| 90–100 · transitional (20–25) † | 14 | 14 | 14 | 33% | 29% | +0.92 | -0.98 | -0.22 |

### Factor · ADX
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| supportive | 138 | 138 | 138 | 46% | 45% | +1.21 | -0.86 | +0.24 |
| neutral | 676 | 676 | 676 | 39% | 44% | +1.30 | -1.25 | +0.01 |
| against † | 2 | 2 | 2 | 50% | 50% | +1.32 | -0.86 | +0.59 |

### Factor · BEARISH_ENGULFING
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| supportive | 227 | 227 | 227 | 47% | 43% | +1.11 | -0.92 | +0.12 |
| neutral | 589 | 589 | 589 | 37% | 45% | +1.35 | -1.28 | +0.02 |

### Factor · BULLISH_ENGULFING
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| supportive | 199 | 199 | 199 | 47% | 43% | +1.10 | -1.06 | +0.12 |
| neutral | 617 | 617 | 617 | 38% | 45% | +1.34 | -1.22 | +0.03 |

### Factor · DARK_CLOUD_COVER
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| neutral | 775 | 775 | 775 | 41% | 45% | +1.31 | -1.19 | +0.08 |
| supportive | 41 | 41 | 41 | 29% | 32% | +0.89 | -1.11 | -0.40 |

### Factor · EVENING_STAR
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| neutral | 767 | 767 | 767 | 41% | 44% | +1.30 | -1.17 | +0.07 |
| supportive | 49 | 49 | 49 | 29% | 41% | +1.09 | -1.41 | -0.28 |

### Factor · FIBONACCI
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| neutral | 781 | 781 | 781 | 40% | 44% | +1.29 | -1.19 | +0.05 |
| supportive | 35 | 35 | 35 | 35% | 37% | +1.06 | -0.95 | +0.01 |

### Factor · MACD_CROSS
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| neutral | 682 | 682 | 682 | 41% | 44% | +1.33 | -1.22 | +0.10 |
| supportive | 134 | 134 | 134 | 33% | 43% | +1.03 | -1.02 | -0.18 |

### Factor · MACD_HISTOGRAM
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| neutral | 725 | 725 | 725 | 40% | 44% | +1.28 | -1.16 | +0.06 |
| supportive | 91 | 91 | 91 | 37% | 48% | +1.32 | -1.40 | +0.00 |

### Factor · MORNING_STAR
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| supportive | 46 | 46 | 46 | 45% | 48% | +1.19 | -0.91 | +0.25 |
| neutral | 770 | 770 | 770 | 40% | 44% | +1.29 | -1.20 | +0.04 |

### Factor · MULTIBAGGER_EMA
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| supportive | 112 | 112 | 112 | 29% | 47% | +1.45 | -1.00 | +0.14 |
| neutral | 704 | 704 | 704 | 42% | 44% | +1.26 | -1.21 | +0.04 |

### Factor · PIERCING_PATTERN
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| supportive | 20 | 20 | 20 | 47% | 50% | +1.14 | -1.31 | +0.21 |
| neutral | 796 | 796 | 796 | 40% | 44% | +1.29 | -1.18 | +0.05 |

### Factor · PRICE_VS_EMA
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| neutral | 741 | 741 | 741 | 40% | 45% | +1.31 | -1.20 | +0.06 |
| supportive | 75 | 75 | 75 | 39% | 40% | +1.00 | -1.04 | +0.01 |

### Factor · RSI_DIVERGENCE
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| supportive | 63 | 63 | 63 | 27% | 70% | +3.30 | -2.84 | +0.43 |
| neutral | 753 | 753 | 753 | 41% | 42% | +1.12 | -1.04 | +0.02 |

### Factor · RSI_LEVEL
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| neutral | 684 | 684 | 684 | 42% | 44% | +1.30 | -1.12 | +0.10 |
| supportive | 132 | 132 | 132 | 31% | 42% | +1.23 | -1.50 | -0.17 |

### Factor · SR_ZONE
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| neutral | 227 | 227 | 227 | 35% | 48% | +1.70 | -1.47 | +0.06 |
| supportive | 589 | 589 | 589 | 42% | 43% | +1.13 | -1.07 | +0.05 |

### Factor · VOLUME
| Cell | n | entered | meas | hit | reach1R | mfe R | mae R | exp R |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| neutral | 681 | 681 | 681 | 40% | 45% | +1.32 | -1.21 | +0.06 |
| supportive | 135 | 135 | 135 | 41% | 40% | +1.11 | -1.07 | +0.02 |

† n < 20 — shown for completeness, not ranked (insufficient sample).