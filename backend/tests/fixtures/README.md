# Vision fixtures

`hand_drawn_parallel_quality_workflow.png` is a generated photograph used by the opt-in live vision test.

Expected graph:

- 9 nodes
- 11 directed connections
- `Customer Brief` fans out to three research nodes
- the three research nodes merge at `Synthesize Findings`
- `Evidence Complete?` routes YES to `Write Launch Plan` and NO through `Human Review`
- `Write Launch Plan` ends at `Publish Report`

Run only the live fixture after adding provider environment variables:

```bash
RUN_LIVE_VISION_TESTS=1 .venv/bin/pytest -q tests/test_live_vision_fixture.py -m live_vision
```
