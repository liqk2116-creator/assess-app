import json
import os
import tempfile

def test_import_quiz_script_runs():
    # 用临时数据库，避免污染 app.db
    with tempfile.TemporaryDirectory() as d:
        os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

        # 生成一个最小 JSON（覆盖：likert + forced_choice + situational）
        payload = {
            "version": "test_v1",
            "language": "zh",
            "generated_at_utc": "2026-02-05T00:00:00Z",
            "schema": {"scale": {"min": 1, "max": 5}},
            "axes": [
                {
                    "axis": "A",
                    "axis_name": "Axis A",
                    "groups": [
                        {
                            "group_id": "A1",
                            "title": "Likert Group",
                            "type": "likert_1_5",
                            "pick_rule": "single",
                            "items": [
                                {
                                    "item_id": "A1.1",
                                    "prompt": "Q1",
                                    "reverse": False,
                                    "measure": {"axis": "A", "axis_name": "Axis A", "group_id": "A1"},
                                }
                            ],
                        }
                    ],
                }
            ],
            "forced_choice": [
                {
                    "id": "FC1",
                    "type": "forced_choice_2",
                    "pick_rule": "single",
                    "shuffle_options": True,
                    "prompt": "FC prompt",
                    "options": [
                        {"option_id": "A", "text": "optA", "effects": [{"trait": "t1", "delta": 1}]},
                        {"option_id": "B", "text": "optB", "effects": [{"trait": "t1", "delta": -1}]},
                    ],
                }
            ],
            "situational": [
                {
                    "group_id": "S1",
                    "title": "Situational",
                    "type": "situational_best_worst",
                    "pick_rule": "best_worst",
                    "ui_mode": "best_worst",
                    "constraints": {"best": 1, "worst": 1},
                    "items": [
                        {
                            "item_id": "S1.1",
                            "prompt": "S prompt",
                            "shuffle_options": True,
                            "options": [
                                {
                                    "option_id": "O1",
                                    "text": "o1",
                                    "effects_best": [{"trait": "t2", "delta": 1}],
                                    "effects_worst": [{"trait": "t2", "delta": -1}],
                                }
                            ],
                        }
                    ],
                }
            ],
        }

        json_path = os.path.join(d, "quiz.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)

        # 直接调用模块 main（避免 subprocess 复杂）
        from app import import_quiz  # noqa
        code = import_quiz.main(["app.import_quiz", json_path])
        assert code == 0

os.environ.pop("DATABASE_URL", None)

