import json
import sys
import types

from transcript_polish import cli


class DummyModelInputs(dict):
    def __init__(self):
        super().__init__(input_ids=[[1, 2]])
        self.input_ids = [[1, 2]]

    def to(self, _device):
        return self


class DummyTokenizer:
    def __call__(self, _texts, return_tensors=None):
        assert return_tensors == "pt"
        return DummyModelInputs()

    def batch_decode(self, _generated_ids, skip_special_tokens=True):
        assert skip_special_tokens is True
        return ["decoded"]


class DummyModel:
    def __init__(self):
        self.kwargs = None

    def generate(self, **kwargs):
        self.kwargs = kwargs
        return [[1, 2, 3]]


class DummyNoGrad:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


def test_default_prompt_preserves_english_and_speaker_labels():
    prompt_config = cli.get_default_prompt_config()
    messages = cli.build_messages(
        "[00:01:12] SPEAKER_00: 我覺得這個很 low",
        "",
        "",
        prompt_config,
    )

    assert "不要把正確英文口語翻成中文" in messages[0]["content"]
    assert "SPEAKER_XX" in messages[0]["content"]
    assert "保留原始口語、講者標記與正確英文用語" in messages[1]["content"]


def test_load_prompt_config_from_json(tmp_path):
    config_path = tmp_path / "prompt.json"
    payload = {
        "system_prompt": "system",
        "repair_prompt": "repair",
        "final_user_instruction": "final",
        "repair_user_instruction": "repair-user",
    }
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    prompt_config = cli.load_prompt_config(str(config_path))

    assert prompt_config.system_prompt == "system"
    assert prompt_config.repair_user_instruction == "repair-user"


def test_generate_response_uses_max_new_tokens(monkeypatch):
    model = DummyModel()
    tokenizer = DummyTokenizer()
    loaded_model = cli.LoadedModel(
        tokenizer=tokenizer,
        model=model,
        device="cpu",
        dtype_name="float32",
        quantization="none",
        input_device="cpu",
        model_memory_bytes="1",
    )
    fake_torch = types.SimpleNamespace(no_grad=lambda: DummyNoGrad())
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    response = cli.generate_response(loaded_model, "prompt")

    assert response == "decoded"
    assert model.kwargs["max_new_tokens"] == cli.MAX_NEW_TOKENS
