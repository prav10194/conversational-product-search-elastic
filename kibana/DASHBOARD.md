# Kibana: the search-analytics dashboard (10 minutes, by hand)

`python -m app.setup_index --kibana` creates two data views: **Search logs** (`search-logs`, time field `@timestamp`)
and **Grocery products**. If it can't reach Kibana, create them in **Stack Management → Data views**.

Run 20–30 searches in the app first so there's data. Include a few that return nothing (e.g. "Ocean Bay vegan under $1").

Then go to **Dashboards → Create dashboard → Create visualization** (Lens). Pick the **Search logs** data view for each panel:

| Panel | Lens setup | What it tells a search team |
|---|---|---|
| Searches over time | Bar, X = `@timestamp`, Y = Count | Traffic shape, peaks |
| Top queries | Table, Rows = Top values of `message.keyword` (10), Metric = Count | What shoppers want most |
| **Zero-result queries** | Table, filter `zero_results : true`, Rows = `message.keyword` | **The #1 search-tuning list**: missing products, synonyms, bad filters |
| Latency | Line, X = `@timestamp`, Y = Median + 95th percentile of `took_ms` | Is search getting slower |
| Diet demand | Donut, Slice by = Top values of `diet_tags` | Which dietary filters matter |
| Claude vs rules | Metric, Count broken down by `understanding` | Is the LLM step working or falling back |
| Mode mix | Bar, Top values of `mode` | hybrid vs lexical (lexical = semantic failed or turned off) |

Save it as **Grocery search analytics**.

Bonus in **Discover** with the **Grocery products** view: `diet_tags : "gluten-free" and price <= 5` shows the same 13
products the app should return for "gluten-free pasta under $5" (in-stock at your store narrows it further).

Interview line: *"I logged every search to its own index: the query, what the LLM extracted, hits, latency. The
zero-results panel is the one a search team lives in, because each row is a synonym to add, a product to stock, or a
filter that's too strict."*
