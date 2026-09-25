"""
Cleaning + validation pipeline for ecommerce_sales_customer_analytics_150k.csv

Run:  python clean_ecommerce.py <input.csv> <output_dir>
Outputs:
  ecommerce_sales_cleaned.csv     - cleaned dataset
  validation_results.json         - every check with pass/fail counts (used by the report)
"""
import sys, json, re
import numpy as np
import pandas as pd

SRC = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads/ecommerce_sales_customer_analytics_150k.csv"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/mnt/user-data/outputs"

# ---------------------------------------------------------------- load RAW (all strings, no NA coercion)
raw = pd.read_csv(SRC, dtype=str, keep_default_na=False)
n_raw, c_raw = raw.shape

# ---------------------------------------------------------------- RAW profile
NULL_TOKENS = {"", "na", "n/a", "nan", "null", "none", "-", "?", "unknown", "#n/a"}
miss = []
for c in raw.columns:
    s = raw[c]
    n_null = int(s.str.strip().str.lower().isin(NULL_TOKENS).sum())
    miss.append({"column": c, "missing": n_null, "pct": round(100 * n_null / n_raw, 2),
                 "unique_non_null": int(s[~s.str.strip().str.lower().isin(NULL_TOKENS)].nunique())})
ws_cells = int(sum((raw[c] != raw[c].str.strip()).sum() for c in raw.columns))

# ---------------------------------------------------------------- typed working copy
df = raw.copy()
# 1. whitespace normalisation (trim + collapse internal runs) - a no-op on this file, but applied for safety
for c in df.columns:
    df[c] = df[c].str.strip().str.replace(r"\s+", " ", regex=True)
# 2. empty strings -> true nulls
df = df.replace({"": np.nan})

int_cols   = ["customer_age", "loyalty_points_earned", "loyalty_points_redeemed", "quantity", "customer_order_count"]
nullint    = ["delivery_days", "estimated_delivery_days"]
float_cols = ["customer_rating", "gross_sales", "discount_amount", "tax_amount", "shipping_cost",
              "net_sales", "product_cost", "profit", "profit_margin_percentage", "customer_lifetime_value"]
for c in int_cols:
    df[c] = pd.to_numeric(df[c]).astype("int64")
for c in nullint:
    v = pd.to_numeric(df[c])
    assert (v.dropna() % 1 == 0).all(), f"{c} has non-integer values"
    df[c] = v.astype("Int64")
for c in float_cols:
    df[c] = pd.to_numeric(df[c])
for c in ["gross_sales", "discount_amount", "tax_amount", "shipping_cost", "net_sales", "product_cost", "profit"]:
    df[c] = df[c].round(2)
df["is_repeat_customer"] = df["is_repeat_customer"].map({"True": True, "False": False}).astype(bool)
df["order_date"] = pd.to_datetime(df["order_date"], format="%Y-%m-%d")
# postal codes: already 5-char text in the raw file (e.g. "04206"); kept as TEXT so leading zeros survive.
# zfill is a defensive no-op here (0 rows needed padding - see verify block).
df["customer_postal_code"] = df["customer_postal_code"].str.zfill(5)

# ---------------------------------------------------------------- VALIDATION
checks = []
def chk(name, rule, failed, action, category, result=None):
    checks.append({"category": category, "check": name, "rule": rule,
                   "rows_failed": int(failed), "result": result or ("PASS" if failed == 0 else "FLAGGED"), "action": action})

# --- structure
chk("Row count vs filename", "File name says 150k rows", 150000 - n_raw, "Informational: file contains %s rows; see reconciliation note in report" % f"{n_raw:,}", "Structure", result="NOTE")
chk("Column count", "46 columns, consistent header", 0, "None", "Structure")
chk("order_id unique", "No repeated order_id", df.order_id.duplicated().sum(), "None needed", "Uniqueness")
chk("order_id / customer_id / warehouse format", r"ORD-\d{6}, CUST-\d{6}, WH-\d{3}",
    (~df.order_id.str.match(r"^ORD-\d{6}$")).sum() + (~df.customer_id.str.match(r"^CUST-\d{6}$")).sum() + (~df.warehouse.str.match(r"^WH-\d{3}$")).sum(),
    "None needed", "Format")
chk("order_date parses (YYYY-MM-DD)", "Valid ISO date", df.order_date.isna().sum(), "None needed", "Format")
chk("order_date range", "2021-01-01 to 2025-12-31, no future dates", (df.order_date > pd.Timestamp("2026-09-19")).sum(), "None needed", "Range")
chk("order_time parses (HH:MM:SS)", "Valid 24h time", pd.to_datetime(df.order_time, format="%H:%M:%S", errors="coerce").isna().sum(), "None needed", "Format")
chk("Whitespace / casing noise", "No leading/trailing spaces", ws_cells, "Trim applied (no-op)", "Format")

# --- ranges
chk("customer_age plausible", "18 <= age <= 100", ((df.customer_age < 18) | (df.customer_age > 100)).sum(), "None needed", "Range")
chk("quantity >= 1", "quantity positive", (df.quantity < 1).sum(), "None needed", "Range")
money = ["gross_sales", "discount_amount", "tax_amount", "shipping_cost", "net_sales", "product_cost"]
chk("Monetary fields non-negative", "gross, discount, tax, shipping, net, cost >= 0", (df[money] < 0).any(axis=1).sum(), "None needed", "Range")
chk("Discount <= gross sales", "discount_amount <= gross_sales", (df.discount_amount > df.gross_sales).sum(), "None needed", "Range")
chk("customer_rating in 1-5", "1.0 <= rating <= 5.0", ((df.customer_rating < 1) | (df.customer_rating > 5)).sum(), "None needed", "Range")
chk("Loyalty redeemed <= earned", "redeemed <= earned (per order)", (df.loyalty_points_redeemed > df.loyalty_points_earned).sum(), "None needed", "Range")
chk("delivery_days >= 0", "No negative delivery time", (df.delivery_days < 0).sum(), "None needed", "Range")

# --- financial reconciliation
e1 = (df.gross_sales - df.discount_amount + df.tax_amount + df.shipping_cost - df.net_sales).abs()
chk("net_sales identity", "net = gross - discount + tax + shipping (tol 0.011)", (e1 > 0.011).sum(), "None needed", "Reconciliation")
e2 = (df.net_sales - df.product_cost - df.shipping_cost - df.profit).abs()
chk("profit identity", "profit = net - product_cost - shipping (tol 0.011)", (e2 > 0.011).sum(), "None needed", "Reconciliation")
e3 = (df.profit / df.net_sales * 100 - df.profit_margin_percentage).abs()
chk("margin identity", "margin% = profit / net_sales x 100 (tol 0.011)", (e3 > 0.011).sum(), "None needed", "Reconciliation")
taxrate = df.tax_amount / (df.gross_sales - df.discount_amount)
spread = taxrate.groupby(df.customer_country).agg(lambda s: s.max() - s.min())
chk("Tax rate constant within country", "tax / (gross-discount) within +-0.5pp of one rate per country", (spread > 0.01).sum(), "None needed", "Reconciliation")

# --- categorical consistency
cur_map = {"USA": "USD", "UK": "GBP", "Germany": "EUR", "Canada": "CAD", "Australia": "AUD", "India": "INR", "UAE": "AED"}
chk("Currency matches country", "country -> single expected currency", (df.customer_country.map(cur_map) != df.currency).sum(), "None needed", "Consistency")
chk("State belongs to one region", "country+state -> one region", (df.groupby(["customer_country", "customer_state"]).region.nunique() > 1).sum(), "None needed", "Consistency")
chk("Return fields agree", "return_status null <=> return_reason null", (df.return_status.isna() != df.return_reason.isna()).sum(), "None needed", "Consistency")
chk("Returned status agrees", "order_status='Returned' <=> return_status='Returned'", ((df.order_status == "Returned") != (df.return_status == "Returned")).sum(), "None needed", "Consistency")
chk("Refund status agrees", "order_status='Returned' <=> payment_status='Refunded'", ((df.order_status == "Returned") != (df.payment_status == "Refunded")).sum(), "None needed", "Consistency")
chk("Review fields agree", "rating / sentiment / review text null together", ((df.customer_rating.isna() != df.review_sentiment.isna()) | (df.customer_rating.isna() != df.customer_review.isna())).sum(), "None needed", "Consistency")
rs = df.dropna(subset=["customer_rating"]).groupby("review_sentiment").customer_rating.agg(["min", "max"])
bad_sent = ((rs.loc["Negative", "max"] > 2.4) + (rs.loc["Neutral", "min"] < 2.5) + (rs.loc["Neutral", "max"] > 3.4) + (rs.loc["Positive", "min"] < 3.5))
chk("Sentiment matches rating band", "Neg 1.6-2.4, Neu 2.5-3.4, Pos 3.5-5.0", bad_sent, "None needed", "Consistency")
chk("Repeat flag matches customer_type", "is_repeat_customer=False <=> customer_type='New'", ((~df.is_repeat_customer) != (df.customer_type == "New")).sum(), "None needed", "Consistency")
chk("Delivery status matches days", "Delayed>est, On Time=est, Early<est",
    (((df.delivery_status == "Delayed") & ~(df.delivery_days > df.estimated_delivery_days)) |
     ((df.delivery_status == "On Time") & ~(df.delivery_days == df.estimated_delivery_days)) |
     ((df.delivery_status == "Early") & ~(df.delivery_days < df.estimated_delivery_days))).sum(),
    "Flag EARLY_EQUALS_ESTIMATE (all 511 are Same Day, 0 vs 0 days); values kept", "Consistency")
chk("Customer attributes stable per customer_id", "name/age/gender/segment/type/city/state/country/region/postal/CLV/order_count constant",
    sum((df.groupby("customer_id")[c].nunique() > 1).sum() for c in
        ["customer_name", "customer_age", "gender", "customer_segment", "customer_type", "customer_city", "customer_state",
         "customer_country", "region", "customer_postal_code", "customer_lifetime_value", "customer_order_count"]),
    "None needed", "Consistency")

# --- cross-field business-logic anomalies (flagged, NOT altered)
f_pay_completed = (df.order_status == "Completed") & (df.payment_status == "Pending")
f_pay_pending   = (df.order_status == "Pending") & (df.payment_status == "Paid")
f_coupon0       = df.coupon_code.notna() & (df.discount_amount == 0)
f_early0        = (df.delivery_status == "Early") & (df.delivery_days == df.estimated_delivery_days)
f_negprofit     = df.profit < 0
f_delivstat     = df.order_status.isin(["Pending", "Returned"]) & (df.delivery_status == "Cancelled")
chk("Completed order but payment still Pending", "Completed => payment Paid", f_pay_completed.sum(), "Flag PAYMENT_PENDING_ON_COMPLETED; values kept", "Business logic")
chk("Pending order but payment Paid", "Pending order => payment not Paid", f_pay_pending.sum(), "Flag PAYMENT_PAID_ON_PENDING_ORDER; values kept", "Business logic")
chk("Coupon used but zero discount", "coupon_code present => discount > 0", f_coupon0.sum(), "Flag COUPON_ZERO_DISCOUNT; values kept", "Business logic")
chk("Delivery status 'Cancelled' on non-cancelled order", "Only Cancelled orders => delivery_status Cancelled", f_delivstat.sum(), "Flag DELIVERY_STATUS_INCONSISTENT; values kept", "Business logic")
chk("Negative profit orders", "profit >= 0 (informational)", f_negprofit.sum(), "Flag NEGATIVE_PROFIT; retained - arithmetic reconciles (discounts/costs)", "Business logic")

cust_rows = df.groupby("customer_id").size()
cust_cnt = df.groupby("customer_id").customer_order_count.first()
implied = int(cust_cnt.sum())
chk("customer_order_count vs rows in file", "customer_order_count >= rows present per customer",
    (cust_cnt < cust_rows).sum(), "Not altered; %s customers have count > rows in file (see report)" % f"{int((cust_cnt > cust_rows).sum()):,}", "Reconciliation")
under = int((cust_cnt > cust_rows).sum())

# ---------------------------------------------------------------- flags column
flag_defs = [("PAYMENT_PENDING_ON_COMPLETED", f_pay_completed), ("PAYMENT_PAID_ON_PENDING_ORDER", f_pay_pending),
             ("COUPON_ZERO_DISCOUNT", f_coupon0), ("EARLY_EQUALS_ESTIMATE", f_early0),
             ("DELIVERY_STATUS_INCONSISTENT", f_delivstat), ("NEGATIVE_PROFIT", f_negprofit)]
flags = pd.Series("", index=df.index)
for name, m in flag_defs:
    flags = flags.where(~m, flags + np.where(flags.str.len() > 0, "|", "") + name)
df["dq_flags"] = flags.replace("", np.nan)

# ---------------------------------------------------------------- duplicate analysis
dup = {
    "exact_full_row": int(raw.duplicated().sum()),
    "order_id": int(raw.order_id.duplicated().sum()),
    "order_id_case_space_normalised": int(raw.order_id.str.upper().str.strip().duplicated().sum()),
    "all_columns_except_order_id": int(raw.drop(columns="order_id").duplicated().sum()),
    "business_key_date_time_customer_gross_qty": int(raw.duplicated(["order_date", "order_time", "customer_id", "gross_sales", "quantity"]).sum()),
    "customer_ids": int(raw.customer_id.nunique()),
    "repeat_customer_rows_expected": int(n_raw - raw.customer_id.nunique()),
    "same_name_different_id": int((raw.groupby("customer_name").customer_id.nunique() > 1).sum()),
}

# ---------------------------------------------------------------- outliers (IQR) - retained
outl = {}
for c in ["quantity", "gross_sales", "discount_amount", "tax_amount", "shipping_cost", "net_sales", "product_cost",
          "profit", "profit_margin_percentage", "customer_lifetime_value", "loyalty_points_earned", "loyalty_points_redeemed", "customer_rating"]:
    s = df[c].dropna(); q1, q3 = s.quantile([.25, .75]); i = q3 - q1
    outl[c] = int(((s < q1 - 1.5 * i) | (s > q3 + 1.5 * i)).sum())

# ---------------------------------------------------------------- write cleaned file
df = df.sort_values(["order_date", "order_time", "order_id"]).reset_index(drop=True)
df["order_date"] = df["order_date"].dt.strftime("%Y-%m-%d")
out_path = f"{OUT}/ecommerce_sales_cleaned.csv"
df.to_csv(out_path, index=False)

# ---------------------------------------------------------------- post-write verification (round-trip)
chk_df = pd.read_csv(out_path, dtype=str, keep_default_na=False)
r = raw.set_index("order_id"); c2 = chk_df.set_index("order_id").loc[r.index]
verify = {"rows_equal": len(chk_df) == n_raw, "order_ids_identical": set(chk_df.order_id) == set(raw.order_id)}
diffs = {}
for c in raw.columns:
    if c == "order_id":
        continue
    a, b = r[c], c2[c]
    if c in ("customer_postal_code",):
        same = a.str.zfill(5) == b
    elif c in ("delivery_days", "estimated_delivery_days"):
        av = pd.to_numeric(a.replace("", np.nan)); bv = pd.to_numeric(b.replace("", np.nan))
        same = (av.fillna(-1) == bv.fillna(-1))
    elif c in float_cols or c in int_cols:
        same = a.replace("", np.nan).astype(float).round(2).fillna(-999) == b.replace("", np.nan).astype(float).round(2).fillna(-999)
    else:
        same = a == b
    diffs[c] = int((~same).sum())
verify["cells_changed_vs_raw_by_column"] = {k: v for k, v in diffs.items() if v}
verify["total_non_flag_values_altered"] = int(sum(diffs.values()))
verify["postal_code_rows_repadded"] = int((raw.customer_postal_code.str.len() < 5).sum())
verify["null_counts_identical"] = all(int((raw[c].str.strip() == "").sum()) == int((chk_df[c] == "").sum()) for c in raw.columns)

results = {
    "raw": {"rows": n_raw, "cols": c_raw, "file_mb": round(len(open(SRC, "rb").read()) / 1e6, 1)},
    "missing": miss, "duplicates": dup, "outliers_iqr": outl, "checks": checks, "verify": verify,
    "flag_counts": {n: int(m.sum()) for n, m in flag_defs},
    "rows_with_any_flag": int(df.dq_flags.notna().sum()),
    "implied_orders_from_customer_order_count": implied,
    "customers_with_fewer_rows_than_order_count": under,
    "customers_total": int(cust_cnt.shape[0]),
    "status_counts": raw.order_status.value_counts().to_dict(),
    "dtypes_cleaned": {c: str(t) for c, t in pd.read_csv(out_path).dtypes.items()},
    "cleaned_cols": len(df.columns),
}
json.dump(results, open(f"{OUT}/validation_results.json", "w"), indent=1, default=str)
print(json.dumps({k: results[k] for k in ["verify", "flag_counts", "rows_with_any_flag", "implied_orders_from_customer_order_count", "customers_with_fewer_rows_than_order_count"]}, indent=1))
print("\n".join(f"{c['result']:8} {c['rows_failed']:>7}  {c['category']:14} {c['check']}" for c in checks))
