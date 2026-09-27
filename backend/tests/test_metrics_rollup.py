import asyncio

from workbench.infrastructure.metrics_rollup import roll_up_provider_metrics


class Session:
    def __init__(self):
        self.statements = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def begin(self):
        return self

    async def execute(self, statement):
        self.statements.append(str(statement))


def test_metrics_rollup_upserts_hourly_and_daily_buckets():
    session = Session()
    asyncio.run(roll_up_provider_metrics(lambda: session))
    assert len(session.statements) == 2
    assert "provider_metrics_hourly" in session.statements[0]
    assert "ON CONFLICT" in session.statements[0]
    assert "provider_metrics_daily" in session.statements[1]
