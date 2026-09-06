# F1 — would a market-cap SIZE floor have helped? (2026-09-07)

**The half of F1 that needs no vendor.** MCE 5b proposes a market-cap floor on the
junk gate; building it means choosing a fundamentals vendor (**decision D3**) and
paying for an XBRL scraper. The standing instruction is to *cross-tab a cheap proxy
first*, because 5a already found the illiquid cohort net-**positive** and so
questioned 5b's premise.

**105 closed paper positions.** We have no `market_cap` (no writer — that
is what 5b would build), so we test the two things such a floor would be proxying
for: **median daily traded value** and **entry price level**.

⭐ **The decisive test: if size matters, both proxies should point the same way.**
Two measures of one underlying quantity that disagree are not measuring it.

## By median daily traded value (Q1 = smallest / least traded)

| quintile | n | median traded value | mean return | win | total |
|---|---|---|---|---|---|
| Q1 | 21 | 0.42 Cr | +1.517% | 67% | ₹9,791 |
| Q2 | 21 | 2.89 Cr | -0.153% | 52% | ₹-15,294 |
| Q3 | 21 | 9.24 Cr | +1.285% | 62% | ₹12,573 |
| Q4 | 21 | 37.90 Cr | -0.296% | 29% | ₹-11,866 |
| Q5 | 21 | 254.25 Cr | -0.443% | 48% | ₹-5,423 |

Q1 − Q5 mean-return difference: 90% interval **[-0.083%, +3.957%]**

## By entry price level (Q1 = cheapest)

| quintile | n | avg entry price | mean return | win | total |
|---|---|---|---|---|---|
| Q1 | 21 | 67.34 ₹ | -0.703% | 52% | ₹-6,119 |
| Q2 | 21 | 242.34 ₹ | -0.074% | 38% | ₹-18,505 |
| Q3 | 21 | 525.46 ₹ | +1.567% | 67% | ₹12,971 |
| Q4 | 21 | 1,192.54 ₹ | +0.911% | 57% | ₹-8,375 |
| Q5 | 21 | 3,518.42 ₹ | +0.210% | 43% | ₹9,811 |

Q1 − Q5 mean-return difference: 90% interval **[-3.220%, +1.473%]**

## Verdict

⛔ **THE TWO SIZE PROXIES DISAGREE — AND NEITHER CONTRAST IS ESTABLISHED.**

- traded-value Q1−Q5 interval **SPANS zero**
- price-level Q1−Q5 interval **SPANS zero**

So the case against a size floor is doubled: the two proxies point in opposite
directions, *and* neither difference survives its own bootstrap. There is no
coherent size signal here to build a gate on.

- By traded value, the **smallest** quintile is better than the largest.
- By price level, the **cheapest** quintile is worse than the dearest.

If a size effect were driving outcomes, two proxies for size would point the
same way. They do not, and neither is monotonic across its own quintiles.

**⇒ The cheap evidence gives a market-cap floor NO support.** That does not
prove such a floor would fail — only that paying a vendor to test a hypothesis
the free data already declines to support is the expensive way to learn it.

**Recommendation: DROP MCE 5b, and D3 (the vendor decision) becomes moot until
someone produces a reason to revisit the premise.** This is consistent with the
5a ruling — where the liquidity floor would have cut a net-*winning* set, and
the already-ACTIVE diversity gate caught the SRTL archetype anyway.

## ⚠ What this cannot tell you

- **n = 105 closed positions, 21 per quintile.** Nothing here approaches the
  project's t ≈ 3.6 promotion bar, and that bar does not fall with n.
- **Traded value is not market cap.** A widely-traded small company and a quiet
  large one both break the proxy. This is evidence about *sequencing*, not a
  measurement of the size factor.
- **Survivorship**: these are the names our engine chose, not a cross-section of
  the market. A size effect could exist in the universe and be invisible here.
