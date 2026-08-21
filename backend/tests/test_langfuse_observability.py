from libs.langchain.langfuse_client import langchain_config, trace_scope, verify_connection


def test_disabled_langfuse_is_a_clean_noop() -> None:
    verify_connection()
    assert langchain_config("test-run") == {"run_name": "test-run"}
    with trace_scope("test-trace") as observation:
        observation.update(output={"ok": True})
