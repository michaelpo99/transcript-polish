from __future__ import annotations

from collections.abc import Iterable

from . import cli


def normalize_eos_token_ids(*values) -> set[int]:
    result: set[int] = set()
    for value in values:
        if value is None:
            continue
        if isinstance(value, int):
            result.add(value)
            continue
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            for item in value:
                if isinstance(item, int):
                    result.add(item)
    return result


def output_is_truncated(
    generated_token_ids,
    *,
    max_new_tokens: int,
    eos_token_ids: set[int],
) -> bool:
    token_count = len(generated_token_ids)
    if token_count < max_new_tokens:
        return False
    if not generated_token_ids:
        return False

    last_token = generated_token_ids[-1]
    if hasattr(last_token, "item"):
        last_token = last_token.item()
    return not eos_token_ids or int(last_token) not in eos_token_ids


def generate_response_checked(loaded_model: cli.LoadedModel, prompt_text: str) -> str:
    model = loaded_model.model
    tokenizer = loaded_model.tokenizer

    try:
        import torch  # type: ignore
    except ModuleNotFoundError as exc:
        raise cli.UserFacingError("錯誤：執行時找不到 torch。") from exc

    model_inputs = tokenizer([prompt_text], return_tensors="pt").to(
        loaded_model.input_device
    )
    with torch.no_grad():
        output_ids = model.generate(
            **model_inputs,
            max_new_tokens=cli.MAX_NEW_TOKENS,
            do_sample=False,
        )

    generated_batches = [
        full_output_ids[len(input_ids) :]
        for input_ids, full_output_ids in zip(model_inputs.input_ids, output_ids)
    ]
    generated_token_ids = generated_batches[0]

    eos_token_ids = normalize_eos_token_ids(
        getattr(getattr(model, "generation_config", None), "eos_token_id", None),
        getattr(getattr(model, "config", None), "eos_token_id", None),
        getattr(tokenizer, "eos_token_id", None),
    )
    if output_is_truncated(
        generated_token_ids,
        max_new_tokens=cli.MAX_NEW_TOKENS,
        eos_token_ids=eos_token_ids,
    ):
        raise cli.UserFacingError(
            "錯誤：模型輸出達到上限 "
            f"{cli.MAX_NEW_TOKENS} tokens，內容未完整輸出。"
            "此檔案不會寫入正式輸出；請縮短輸入，或等待後續長文切塊功能。"
        )

    return tokenizer.batch_decode(generated_batches, skip_special_tokens=True)[0]
