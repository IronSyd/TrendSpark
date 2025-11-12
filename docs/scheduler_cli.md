# Scheduler CLI

Use the CLI to manage scheduler configs without hitting the worker API.

`
python -m trend_spark_ai.cli scheduler-list
python -m trend_spark_ai.cli scheduler-add ingest_rank "*/10 * * * *" --name "fast ingest" --parameters '{"max_x":50}'
python -m trend_spark_ai.cli scheduler-update 3 --enable --priority 3
python -m trend_spark_ai.cli scheduler-delete 5
python -m trend_spark_ai.cli scheduler-refresh
`

scheduler-add and scheduler-update accept job-specific parameters as JSON. Available job IDs:

- ingest_rank
- gen_replies
- daily_ideas

Changes take effect immediately on running worker instances via efresh_scheduler_jobs().
