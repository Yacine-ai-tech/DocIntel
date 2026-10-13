import pytest
from core import keypool as kp


def env(**kw):
    return dict(kw)


def test_discovery_is_env_driven_and_ordered():
    e = env(GROQ_API_KEY="a", GROQ_API_KEY_2="b", GROQ_API_KEY_10="c", GROQ_API_KEY_x="d", OTHER_API_KEY="z")
    assert kp.discover("groq", e) == ["a", "b", "c", "d"]


def test_list_variable_and_dedupe():
    e = env(GEMINI_API_KEY="a", GEMINI_API_KEYS="a, b c,d")
    assert kp.discover("gemini", e) == ["a", "b", "c", "d"]


def test_slots_pin_a_subset():
    e = env(GROQ_API_KEY="a", GROQ_API_KEY_2="b", GROQ_API_KEY_3="c", GROQ_KEY_SLOTS="2,3")
    assert kp.discover("groq", e) == ["b", "c"]


def test_round_robin_and_cooldown():
    pool = kp.KeyPool("groq", ["a", "b", "c"])
    seen = [pool.acquire().key for _ in range(3)]
    assert sorted(seen) == ["a", "b", "c"]
    lease = pool.acquire()
    pool.cool_down(lease, 60)
    keys = {pool.acquire().key for _ in range(6)}
    assert lease.key not in keys
    assert pool.available() == 2


def test_call_rotates_on_rate_limit_and_raises_otherwise():
    pool = kp.KeyPool("groq", ["a", "b"])
    used = []

    class Boom(Exception):
        status_code = 429

    def fn(key):
        used.append(key)
        if len(used) == 1:
            raise Boom("rate limit")
        return key

    assert pool.call(fn) in ("a", "b")
    assert len(used) == 2 and used[0] != used[1]

    with pytest.raises(ValueError):
        pool.call(lambda k: (_ for _ in ()).throw(ValueError("bad request")))


def test_all_exhausted():
    pool = kp.KeyPool("groq", ["a"])
    with pytest.raises(kp.AllKeysExhausted):
        pool.call(lambda k: (_ for _ in ()).throw(RuntimeError("429 too many requests")))
    with pytest.raises(kp.AllKeysExhausted):
        kp.KeyPool("groq", []).call(lambda k: k)


def test_retry_after_parsing():
    class E(Exception):
        pass
    e = E("Please retry in 12.5s")
    assert kp.retry_after_seconds(e) == 12.5


def test_model_helpers(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "g1")
    monkeypatch.setenv("GROQ_API_KEY_2", "g2")
    kp.reset()
    assert kp.provider_for_model("groq/openai/gpt-oss-120b") == "groq"
    assert kp.provider_for_model("gemini/gemini-3.5-flash") == "gemini"
    assert kp.provider_for_model("anthropic/claude-haiku-4-5") is None
    first = kp.lease_for_model("groq/x")
    class E(Exception):
        status_code = 429
    assert kp.note_failure(first, E("rate limit")) is True
    second = kp.lease_for_model("groq/x")
    assert second.key != first.key
    assert kp.lease_for_model("anthropic/x") is None
    kp.reset()


def test_acompletion_pooled_passes_key_and_parks_on_rate_limit(monkeypatch):
    import asyncio
    monkeypatch.setenv("GROQ_API_KEY", "g1")
    monkeypatch.setenv("GROQ_API_KEY_2", "g2")
    kp.reset()
    seen = []

    class RL(Exception):
        status_code = 429

    async def fake(model, **kw):
        seen.append(kw.get("api_key"))
        if len(seen) == 1:
            raise RL("rate limit")
        return "ok"

    async def run():
        with pytest.raises(RL):
            await kp.acompletion_pooled(fake, "groq/x", messages=[])
        return await kp.acompletion_pooled(fake, "groq/x", messages=[])

    assert asyncio.run(run()) == "ok"
    assert seen[0] != seen[1] and None not in seen
    kp.reset()
