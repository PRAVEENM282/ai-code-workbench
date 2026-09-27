from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker


async def roll_up_provider_metrics(sessions: async_sessionmaker) -> None:
    """Idempotently refresh completed UTC hourly buckets and daily aggregates."""
    hourly = text("""
      INSERT INTO provider_metrics_hourly
        (id, model_configuration_id, bucket_start, request_count, failure_count,
         latency_histogram)
      SELECT gen_random_uuid(), model_configuration_id,
        date_trunc('hour', created_at), count(*),
        count(*) FILTER (WHERE NOT succeeded),
        jsonb_build_object('lt_250', count(*) FILTER (WHERE latency_ms < 250),
          'lt_1000', count(*) FILTER (WHERE latency_ms >= 250 AND latency_ms < 1000),
          'lt_5000', count(*) FILTER (WHERE latency_ms >= 1000 AND latency_ms < 5000),
          'gte_5000', count(*) FILTER (WHERE latency_ms >= 5000))
      FROM provider_metrics
      WHERE created_at < date_trunc('hour', now())
      GROUP BY model_configuration_id, date_trunc('hour', created_at)
      ON CONFLICT (model_configuration_id, bucket_start) DO UPDATE SET
        request_count=EXCLUDED.request_count, failure_count=EXCLUDED.failure_count,
        latency_histogram=EXCLUDED.latency_histogram
    """)
    daily = text("""
      INSERT INTO provider_metrics_daily
        (id, model_configuration_id, bucket_date, request_count, failure_count,
         latency_histogram)
      SELECT gen_random_uuid(), model_configuration_id, bucket_start::date,
        sum(request_count),
        sum(failure_count), jsonb_build_object(
          'lt_250', sum((latency_histogram->>'lt_250')::bigint),
          'lt_1000', sum((latency_histogram->>'lt_1000')::bigint),
          'lt_5000', sum((latency_histogram->>'lt_5000')::bigint),
          'gte_5000', sum((latency_histogram->>'gte_5000')::bigint))
      FROM provider_metrics_hourly
      WHERE bucket_start < date_trunc('day', now())
      GROUP BY model_configuration_id, bucket_start::date
      ON CONFLICT (model_configuration_id, bucket_date) DO UPDATE SET
        request_count=EXCLUDED.request_count, failure_count=EXCLUDED.failure_count,
        latency_histogram=EXCLUDED.latency_histogram
    """)
    async with sessions() as session, session.begin():
        await session.execute(hourly)
        await session.execute(daily)
