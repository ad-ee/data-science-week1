# data-science-week1
 
Week 1 Objectives
  
By the end of Week 1, interns should be able to:
# Load and inspect tabular datasets using Python tools.
# Identify common data quality issues such as missing values, duplicates, invalid formats.
# Clean datasets systematically and document every major cleaning decision.
# Compute basic KPIs and use them to evaluate business performance.
# Analyze trends in sales and customer behavior.
# Create meaningful charts for communicating analysis outcomes.
# Organize outputs into a clear report structure.
# Submit work professionally through GitHub.

Expected Outcome
Each intern should complete three task-based assignments that show technical correctness,
structured reasoning, and professional presentation quality. Strong submissions will
demonstrate not only code execution, but also thoughtful interpretation and clarity of
communication.

1) Dataset Cleaning 

The raw file was called ecommerce_sales_customer_analytics_150k.csv and honestly it was pretty messy like most real-world data is — random whitespace, string columns that should've been numbers, dates in text form, stuff like that. So I wrote a Python script (clean_ecommerce.py, uses pandas + numpy) to fix all that up and also check the data for weird stuff instead of just blindly trusting it.

Here's what the script actually does, step by step:

Type fixing — converts age, quantity, sales, profit, etc. to actual numbers instead of text. Dates get parsed properly too (order_date, order_time).
Whitespace cleanup — trims extra spaces and fixes empty strings so they become real nulls instead of invisible junk.
Postal codes stay as text — so stuff like 04206 doesn't lose its leading zero (a classic spreadsheet mistake).
A LOT of validation checks — like 30+ checks across different categories:
Structure: are all 46 columns there, is order_id actually unique, etc.
Range checks: is age between 18-100, is quantity always positive, are money fields non-negative, is customer rating between 1-5.
Financial reconciliation: does net_sales actually equal gross - discount + tax + shipping? does profit math check out? (spoiler: it does, math checks out everywhere)
Consistency checks: does the country match the currency (like USA → USD), does the state belong to the right region, do return/refund fields agree with each other.
Business logic flags: stuff like "order says Completed but payment still says Pending" — these get flagged, not deleted, because sometimes weird-looking data is still real data and you don't want to just erase it.
Outlier detection using IQR method, just to know if something's sitting way outside the normal range (again — flagged, not removed).

After all that, the cleaned file has:

Metric	Value
Total rows	138,116
Total columns	47 (46 original + dq_flags column added)
Rows flagged with a data-quality issue	30,720
Countries covered	7
Date range	Jan 1, 2021 – Dec 31, 2025

Nothing important got deleted — sketchy-looking rows just get tagged in a dq_flags column so you know they exist but you still keep the full picture. I think that's the more honest way to clean data tbh, instead of quietly dropping rows and pretending they never existed.

Files:

clean_ecommerce.py → the cleaning + validation script
ecommerce_sales_cleaned.csv → the final cleaned dataset (this is what everything downstream uses)

2) Data Analytics 

Once the data was clean, next step was actually digging into it to find patterns — like which channels make the most money, where returns are coming from, which customers are worth the most, that kind of stuff. This part lives in the ecommerce_sales_customer_analytics_Raw_Data_.xlsx file and feeds straight into the dashboard.

Some of the big takeaways from crunching the numbers:

Total net sales: ~$144.2M across 138k orders
Average profit margin: 43.7% (pretty solid ngl)
Average order value: $1,269.79
Return rate: 6.9% | Cancel rate: 6.1%
Mobile App is the MVP channel — it brings in the most net sales ($57.6M) and profit ($23.9M), even more than the Website.
Consumer segment dominates — they alone account for $79.3M in net sales, way more than Business, Premium, or VIP combined.
Credit Card is the most popular payment method by a good margin (41k+ orders use it).
"Wrong Product" is the #1 return reason, followed by "Other" and "Changed Mind" — so honestly a decent chunk of returns aren't even about product quality, just fit/mismatch stuff.
Sales have a repeating seasonal spike pattern — net sales jump hard around Nov/Dec each year (makes sense, holiday shopping) and dip afterward.

Basically the analytics step is where the raw numbers turn into actual insight — like "oh mobile is doing way better than we thought" or "we should look into why Wrong Product returns are so high."

3) Data Visualization 

Last step — put all that analysis into an actual dashboard so it's easy to read at a glance instead of digging through spreadsheets. This lives in ecommerce_sales_dashboard.xlsx and it's got KPI cards up top plus a bunch of breakdown tables and charts.

Dashboard overview (KPIs + tables)

<img width="860" height="550" alt="dashboard_overview" src="https://github.com/user-attachments/assets/a0f9151c-4b59-4ef3-950b-d129e118785e" />


This part has the big-picture numbers (total sales, margin, return rate, etc.) plus tables breaking things down by channel, region, customer segment, payment method, and more.

Charts

<img width="1419" height="1050" alt="dashboard_charts" src="https://github.com/user-attachments/assets/893de3ba-9266-433b-8763-00bf11b9ae24" />


This is the more visual side — bar charts for sales by channel/region/segment, a pie chart for order status, and a line chart showing the monthly sales & profit trend over the years. You can literally see the holiday-season spikes in that last one.
