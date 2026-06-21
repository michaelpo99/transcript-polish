#!/usr/bin/env python3
import argparse
import importlib.metadata
import importlib.util
import json
import platform
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

DEFAULT_MODEL = "Qwen/Qwen2.5-3B-Instruct"
DEFAULT_OUTPUT_DIR = "formatted"
DEFAULT_QUANTIZATION = "none"
SUPPORTED_EXTENSIONS = {".txt", ".md"}
EXCLUDED_INPUT_NAMES = {"_run-summary.txt", "_environment.txt"}
MAX_NEW_TOKENS = 4096
PROMPT_SAFETY_MARGIN_TOKENS = 512
REPAIR_MIN_RATIO = 0.7
SOURCE_MIN_RATIO = 0.3
GENERIC_TITLE_HINTS = {"逐字稿", "transcript", "formatted", "polished"}

DEFAULT_SYSTEM_PROMPT = """你是一個保守型的繁體中文逐字稿整理助理。你的任務是把 ASR 原始逐字稿整理成可讀、忠實、保留講者原本語氣與詞彙選擇的繁體中文 Markdown。

必須嚴格遵守以下規則：
1. 【忠實】不得摘要、濃縮、改寫成文章、增加資訊、重新闡釋或改變原文資訊順序。
2. 【保留原話】保留講者的口語、語助詞、中英夾雜與原本語氣；不要把正確英文口語翻成中文。
3. 【ASR 修正】只可修正根據上下文高度確定的語音辨識錯字、同音誤字與錯誤斷詞；若無法高度確定，必須保留原文，不得猜測。
4. 【繁體化】將簡體字轉為繁體字形，但不要為了台灣化而改寫原本正確的詞彙或英文用語。
5. 【標點與分段】補上適當標點，並依語意自然停頓切分段落。
6. 【標題】只有在主題自然切換且非常明確時，才加上簡潔 Markdown 標題；短文或單一主題可以完全不加標題。
7. 【講者標記】若原文含有時間戳、SPEAKER_XX、講者代號或類似標記，必須原樣保留，不可重新編號、合併或移動到其他講者。
8. 【禁止雜訊】不要輸出英文說明、分隔線、程式碼區塊標記、模型說明或任何與正文無關的字樣。
9. 【僅輸出結果】直接輸出整理後的 Markdown 正文。"""

DEFAULT_REPAIR_PROMPT = """你是一個保守型的繁體中文逐字稿修稿助理。請根據「原始逐字稿」檢查並修正「整理草稿」。

必須嚴格遵守以下規則：
1. 不得新增原始逐字稿沒有的資訊。
2. 保留講者原本語氣、口語與中英夾雜；不要把原本正確的英文口語翻成中文。
3. 若原文本來就包含英文術語、產品名、指令、路徑、型號、版本號、時間戳或 SPEAKER_XX，必須保留其識別性。
4. 修正 ASR 錯字的目的，是還原講者原話，不是改善遣詞用字或文章化。
5. 不得輸出分隔線、程式碼區塊標記、模型說明文字或其他包裝文字。
6. 只在主題非常明確時才加標題；若全文主題單一，可以不加標題。
7. 最終只輸出可直接存檔的 Markdown 正文。"""

DEFAULT_FINAL_USER_INSTRUCTION = (
    "請直接輸出整理後的繁體中文 Markdown 正文，保留原始口語、講者標記與正確英文用語。"
)
DEFAULT_REPAIR_USER_INSTRUCTION = (
    "請保守修正草稿，只處理高度確定的 ASR 錯字、段落與標點問題；保留原有英文術語、口語與講者標記，直接輸出最終 Markdown。"
)


class UserFacingError(Exception):
    pass


@dataclass
class RuntimeInfo:
    python_version: str
    torch_version: str
    transformers_version: str
    accelerate_version: str
    bitsandbytes_version: str
    cuda_available: bool
    cuda_runtime: str
    gpu_name: str
    gpu_vram_mb: str
    import_error: str


@dataclass
class LoadedModel:
    tokenizer: object
    model: object
    device: str
    dtype_name: str
    quantization: str
    input_device: str
    model_memory_bytes: str


@dataclass
class FileJob:
    input_path: Path
    output_path: Path
    skip: bool


@dataclass(frozen=True)
class PromptConfig:
    system_prompt: str
    repair_prompt: str
    final_user_instruction: str
    repair_user_instruction: str


def load_opencc_converter():
    if importlib.util.find_spec("opencc") is not None:
        from opencc import OpenCC  # type: ignore

        return OpenCC("s2twp")
    return None


def get_default_prompt_config() -> PromptConfig:
    return PromptConfig(
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        repair_prompt=DEFAULT_REPAIR_PROMPT,
        final_user_instruction=DEFAULT_FINAL_USER_INSTRUCTION,
        repair_user_instruction=DEFAULT_REPAIR_USER_INSTRUCTION,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="將 ASR 原始逐字稿保守整理為可讀、忠實的繁體中文 Markdown。"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="只檢查環境與設定，不載入大型模型",
    )
    parser.add_argument("--file", help="處理單一檔案，僅接受 .txt 或 .md")
    parser.add_argument("--dir", help="處理指定目錄第一層的 .txt 與 .md")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="指定 Hugging Face 模型名稱")
    parser.add_argument(
        "--quantization",
        choices=("none", "4bit"),
        default=DEFAULT_QUANTIZATION,
        help="指定模型載入模式，預設為 none",
    )
    parser.add_argument("--replace-dict", help="載入外部替換詞彙表")
    parser.add_argument("--style-guide", help="載入單次任務的額外參考指引")
    parser.add_argument("--prompt-config", help="載入 prompt 設定檔（JSON）")
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="指定輸出子目錄名稱或路徑，預設為 formatted",
    )
    parser.add_argument("-f", "--force", action="store_true", help="覆蓋已存在的輸出檔")
    return parser


def detect_runtime_info() -> RuntimeInfo:
    python_version = platform.python_version()
    torch_version = ""
    transformers_version = ""
    accelerate_version = ""
    bitsandbytes_version = ""
    cuda_available = False
    cuda_runtime = ""
    gpu_name = ""
    gpu_vram_mb = ""
    errors: List[str] = []

    try:
        torch_version = importlib.metadata.version("torch")
    except importlib.metadata.PackageNotFoundError:
        pass
    except Exception as exc:
        errors.append(f"讀取 torch 版本失敗：{exc}")

    try:
        transformers_version = importlib.metadata.version("transformers")
    except importlib.metadata.PackageNotFoundError:
        pass
    except Exception as exc:
        errors.append(f"讀取 transformers 版本失敗：{exc}")

    try:
        accelerate_version = importlib.metadata.version("accelerate")
    except importlib.metadata.PackageNotFoundError:
        pass
    except Exception as exc:
        errors.append(f"讀取 accelerate 版本失敗：{exc}")

    try:
        bitsandbytes_version = importlib.metadata.version("bitsandbytes")
    except importlib.metadata.PackageNotFoundError:
        pass
    except Exception as exc:
        errors.append(f"讀取 bitsandbytes 版本失敗：{exc}")

    if importlib.util.find_spec("torch") is not None:
        try:
            import torch  # type: ignore

            cuda_available = bool(torch.cuda.is_available())
            cuda_runtime = str(getattr(torch.version, "cuda", "") or "")
            if cuda_available:
                gpu_name = str(torch.cuda.get_device_name(0))
                props = torch.cuda.get_device_properties(0)
                gpu_vram_mb = str(int(props.total_memory // (1024 * 1024)))
        except Exception as exc:
            errors.append(f"檢查 torch/CUDA 失敗：{exc}")

    return RuntimeInfo(
        python_version=python_version,
        torch_version=torch_version,
        transformers_version=transformers_version,
        accelerate_version=accelerate_version,
        bitsandbytes_version=bitsandbytes_version,
        cuda_available=cuda_available,
        cuda_runtime=cuda_runtime,
        gpu_name=gpu_name,
        gpu_vram_mb=gpu_vram_mb,
        import_error="; ".join(errors),
    )


def resolve_input_files(args: argparse.Namespace) -> Tuple[List[Path], Path, str]:
    if args.file and args.dir:
        raise UserFacingError("錯誤：--file 與 --dir 不可同時指定。")

    if args.file:
        file_path = Path(args.file).expanduser().resolve()
        validate_input_file(file_path)
        return [file_path], file_path.parent, str(file_path)

    scan_dir = Path(args.dir or ".").expanduser().resolve()
    if not scan_dir.is_dir():
        raise UserFacingError(f"錯誤：目錄不存在：{scan_dir}")

    files = []
    for path in sorted(scan_dir.iterdir()):
        if not path.is_file():
            continue
        if should_skip_input(path, scan_dir / DEFAULT_OUTPUT_DIR):
            continue
        if path.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(path)

    return files, scan_dir, str(scan_dir)


def validate_input_file(path: Path) -> None:
    if not path.exists():
        raise UserFacingError(f"錯誤：檔案不存在：{path}")
    if not path.is_file():
        raise UserFacingError(f"錯誤：不是檔案：{path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise UserFacingError(f"錯誤：不支援的副檔名：{path.suffix or '<none>'}")


def should_skip_input(path: Path, default_output_dir: Path) -> bool:
    if path.name.startswith(".") or path.name.startswith("_"):
        return True
    if path.name in EXCLUDED_INPUT_NAMES:
        return True
    try:
        path.relative_to(default_output_dir)
        return True
    except ValueError:
        return False


def resolve_output_dir(args: argparse.Namespace, base_dir: Path) -> Path:
    output_value = args.output_dir
    candidate = Path(output_value).expanduser()
    if candidate.is_absolute():
        output_dir = candidate.resolve()
    else:
        output_dir = (base_dir / candidate).resolve()
    if output_dir == base_dir.resolve():
        raise UserFacingError("錯誤：輸出目錄不可與輸入 base directory 相同。")
    return output_dir


def load_replace_dict(path_str: Optional[str]) -> Dict[str, str]:
    if not path_str:
        return {}

    path = Path(path_str).expanduser().resolve()
    if not path.is_file():
        raise UserFacingError(f"錯誤：替換詞彙表不存在：{path}")

    replacements: Dict[str, str] = {}
    for line_no, raw_line in enumerate(read_text_file(path).splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=>" not in line:
            raise UserFacingError(
                f"錯誤：替換詞彙表格式錯誤：{path}:{line_no}: {raw_line.rstrip()}"
            )
        source, target = [part.strip() for part in line.split("=>", 1)]
        if not source or not target:
            raise UserFacingError(
                f"錯誤：替換詞彙表格式錯誤：{path}:{line_no}: {raw_line.rstrip()}"
            )
        replacements[source] = target
    return replacements


def resolve_output_path(input_path: Path, output_dir: Path) -> Path:
    return output_dir / f"{input_path.stem}.md"


def build_file_jobs(files: Sequence[Path], output_dir: Path, force: bool) -> List[FileJob]:
    output_map: Dict[Path, Path] = {}
    jobs: List[FileJob] = []
    for input_path in files:
        output_path = resolve_output_path(input_path, output_dir)
        if output_path in output_map:
            other_input = output_map[output_path]
            raise UserFacingError(
                f"錯誤：輸出檔名衝突：{other_input.name} 與 {input_path.name} 都會輸出到 {output_path}"
            )
        output_map[output_path] = input_path
        jobs.append(
            FileJob(
                input_path=input_path,
                output_path=output_path,
                skip=output_path.exists() and not force,
            )
        )
    return jobs


def load_style_guide(path_str: Optional[str]) -> str:
    if not path_str:
        return ""

    path = Path(path_str).expanduser().resolve()
    if not path.is_file():
        raise UserFacingError(f"錯誤：style guide 不存在：{path}")
    return read_text_file(path).strip()


def load_prompt_config(path_str: Optional[str]) -> PromptConfig:
    if not path_str:
        return get_default_prompt_config()

    path = Path(path_str).expanduser().resolve()
    if not path.is_file():
        raise UserFacingError(f"錯誤：prompt config 不存在：{path}")

    try:
        payload = json.loads(read_text_file(path))
    except json.JSONDecodeError as exc:
        raise UserFacingError(
            f"錯誤：prompt config 格式錯誤：{path}:{exc.lineno}:{exc.colno}: {exc.msg}"
        ) from exc

    if not isinstance(payload, dict):
        raise UserFacingError(f"錯誤：prompt config 必須是 JSON object：{path}")

    required_fields = (
        "system_prompt",
        "repair_prompt",
        "final_user_instruction",
        "repair_user_instruction",
    )
    values: Dict[str, str] = {}
    for field_name in required_fields:
        value = payload.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise UserFacingError(
                f"錯誤：prompt config 缺少有效欄位 {field_name}：{path}"
            )
        values[field_name] = value.strip()

    return PromptConfig(**values)


def apply_replacements(content: str, replacements: Dict[str, str]) -> str:
    if not replacements:
        return content
    pattern = re.compile(
        "|".join(
            re.escape(source)
            for source in sorted(replacements.keys(), key=len, reverse=True)
        )
    )
    return pattern.sub(lambda match: replacements[match.group(0)], content)


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def normalize_transcript_text(content: str, converter) -> str:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    if converter is not None:
        normalized = converter.convert(normalized)
    return normalized


def derive_title_hint(input_path: Path) -> str:
    stem = input_path.stem.strip()
    if not stem:
        return ""
    if stem.lower() in GENERIC_TITLE_HINTS:
        return ""
    if not re.search(r"[\u4e00-\u9fff]", stem):
        return ""
    if re.fullmatch(r"[\W_\d]+", stem):
        return ""
    if re.fullmatch(r"[\d\-_/年月日\s]+", stem):
        return ""
    return stem[:30]


def build_messages(
    content: str, style_guide: str, title_hint: str, prompt_config: PromptConfig
) -> List[Dict[str, str]]:
    user_parts = [
        "以下是原始逐字稿：",
        "---",
        content,
        "---",
    ]
    if title_hint:
        user_parts.extend(["", f"檔名主題提示：{title_hint}"])
    if style_guide:
        user_parts.extend(
            [
                "",
                "以下是額外參考規則，僅在不違反原文的前提下使用：",
                style_guide,
            ]
        )
    user_parts.append("")
    user_parts.append(prompt_config.final_user_instruction)
    return [
        {"role": "system", "content": prompt_config.system_prompt},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


def build_repair_messages(
    original_content: str,
    draft: str,
    style_guide: str,
    title_hint: str,
    prompt_config: PromptConfig,
) -> List[Dict[str, str]]:
    user_parts = [
        "以下是原始逐字稿：",
        "---",
        original_content,
        "---",
        "",
        "以下是整理草稿：",
        "---",
        draft,
        "---",
    ]
    if title_hint:
        user_parts.extend(["", f"檔名主題提示：{title_hint}"])
    if style_guide:
        user_parts.extend(
            [
                "",
                "以下是額外參考規則，僅在不違反原文的前提下使用：",
                style_guide,
            ]
        )
    user_parts.extend(["", prompt_config.repair_user_instruction])
    return [
        {"role": "system", "content": prompt_config.repair_prompt},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


def is_wrapper_line(line: str) -> bool:
    normalized = line.strip()
    if not normalized:
        return False
    wrapper_prefixes = (
        "以下是整理後的",
        "以下為整理後的",
        "以下是校正後的",
        "以下為校正後的",
        "這是整理後的",
        "這是校正後的",
    )
    return normalized.startswith(wrapper_prefixes)


def clean_response(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    lines = [line for line in text.splitlines() if line.strip() not in {"---", "***"}]
    while lines and is_wrapper_line(lines[0]):
        lines.pop(0)
    while lines and is_wrapper_line(lines[-1]):
        lines.pop()
    return "\n".join(lines).strip()


def render_prompt(tokenizer, messages: List[Dict[str, str]]) -> str:
    try:
        return tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    except Exception as exc:
        raise UserFacingError(f"錯誤：無法建立模型對話模板：{exc}") from exc


def count_prompt_tokens(tokenizer, prompt_text: str) -> int:
    encoded = tokenizer(prompt_text, return_attention_mask=False)
    return len(encoded["input_ids"])


def get_model_context_limit(loaded_model: LoadedModel) -> int:
    candidates: List[int] = []
    model_limit = getattr(loaded_model.model.config, "max_position_embeddings", None)
    tokenizer_limit = getattr(loaded_model.tokenizer, "model_max_length", None)
    for value in (model_limit, tokenizer_limit):
        if isinstance(value, int) and 0 < value < 1_000_000:
            candidates.append(value)
    if not candidates:
        raise UserFacingError("錯誤：無法判斷模型 context 上限。")
    return min(candidates)


def ensure_prompt_within_budget(
    loaded_model: LoadedModel, prompt_text: str, label: str
) -> None:
    context_limit = get_model_context_limit(loaded_model)
    prompt_tokens = count_prompt_tokens(loaded_model.tokenizer, prompt_text)
    safe_budget = context_limit - MAX_NEW_TOKENS - PROMPT_SAFETY_MARGIN_TOKENS
    if prompt_tokens > safe_budget:
        raise UserFacingError(
            f"錯誤：{label} 過長（prompt_tokens={prompt_tokens}，安全上限={safe_budget}）。"
        )


def normalize_device_name(device_value) -> str:
    if isinstance(device_value, str):
        return device_value
    if isinstance(device_value, int):
        return f"cuda:{device_value}"
    return str(device_value)


def resolve_model_input_device(model) -> str:
    try:
        embeddings = model.get_input_embeddings()
        if embeddings is not None and hasattr(embeddings, "weight"):
            return str(embeddings.weight.device)
    except Exception:
        pass
    device_map = getattr(model, "hf_device_map", None)
    if isinstance(device_map, dict):
        for mapped_device in device_map.values():
            normalized = normalize_device_name(mapped_device)
            if normalized not in {"cpu", "disk"}:
                return normalized
    try:
        first_param = next(model.parameters())
        return str(first_param.device)
    except StopIteration:
        return "cpu"


def get_model_memory_bytes(model) -> str:
    try:
        footprint = model.get_memory_footprint()
    except Exception:
        return "unknown"
    if isinstance(footprint, int) and footprint > 0:
        return str(footprint)
    return "unknown"


def quantized_model_spills_to_cpu(model) -> bool:
    device_map = getattr(model, "hf_device_map", None)
    if not isinstance(device_map, dict):
        return False
    return any(
        normalize_device_name(mapped_device) in {"cpu", "disk"}
        for mapped_device in device_map.values()
    )


def load_model(model_name: str, quantization: str) -> LoadedModel:
    try:
        import torch  # type: ignore
    except ModuleNotFoundError as exc:
        raise UserFacingError(
            "錯誤：缺少 torch。請先在目標 Python 環境安裝 torch。"
        ) from exc

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
    except ModuleNotFoundError as exc:
        raise UserFacingError(
            "錯誤：缺少 transformers。請先在目標 Python 環境安裝 transformers。"
        ) from exc

    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        if not hasattr(tokenizer, "apply_chat_template"):
            raise UserFacingError(
                f"錯誤：模型 tokenizer 不支援 chat template：{model_name}"
            )
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32

        if quantization == "4bit":
            if device != "cuda":
                raise UserFacingError("錯誤：4bit 量化模式目前只支援 CUDA 環境。")
            if importlib.util.find_spec("accelerate") is None:
                raise UserFacingError(
                    "錯誤：4bit 量化模式缺少 accelerate。請先安裝 accelerate。"
                )
            if importlib.util.find_spec("bitsandbytes") is None:
                raise UserFacingError(
                    "錯誤：4bit 量化模式缺少 bitsandbytes。請先安裝 bitsandbytes。"
                )
            from transformers import BitsAndBytesConfig  # type: ignore

            quant_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.float16,
            )
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                quantization_config=quant_config,
                device_map="auto",
                low_cpu_mem_usage=True,
            )
            if quantized_model_spills_to_cpu(model):
                raise UserFacingError(
                    "錯誤：4bit 模型未能完整載入 GPU，已偵測到 CPU/disk offload。"
                    " 請改用較小模型、釋放 GPU 記憶體，或切回 --quantization none。"
                )
            input_device = resolve_model_input_device(model)
            loaded_model = LoadedModel(
                tokenizer=tokenizer,
                model=model,
                device=input_device,
                dtype_name="int4(float16 compute)",
                quantization=quantization,
                input_device=input_device,
                model_memory_bytes=get_model_memory_bytes(model),
            )
        else:
            model = AutoModelForCausalLM.from_pretrained(model_name, dtype=dtype)
            if device == "cuda":
                model = model.to(device)
            loaded_model = LoadedModel(
                tokenizer=tokenizer,
                model=model,
                device=device,
                dtype_name="float16" if device == "cuda" else "float32",
                quantization=quantization,
                input_device=device,
                model_memory_bytes=get_model_memory_bytes(model),
            )

        for attr in ("temperature", "top_p", "top_k"):
            if hasattr(model.generation_config, attr):
                setattr(model.generation_config, attr, None)
        return loaded_model
    except UserFacingError:
        raise
    except Exception as exc:
        hint = ""
        lower = str(exc).lower()
        if "401" in lower or "403" in lower or "gated" in lower or "token" in lower:
            hint = "；若此模型需要授權，請確認 HF_TOKEN 或 Hugging Face CLI 登入狀態"
        elif quantization == "4bit" and (
            "bitsandbytes" in lower or "4-bit" in lower or "4bit" in lower
        ):
            hint = "；請確認已安裝 accelerate、bitsandbytes，且 GPU 記憶體足夠"
        raise UserFacingError(f"錯誤：模型載入失敗：{model_name}: {exc}{hint}") from exc


def generate_response(loaded_model: LoadedModel, prompt_text: str) -> str:
    model = loaded_model.model
    tokenizer = loaded_model.tokenizer

    try:
        import torch  # type: ignore
    except ModuleNotFoundError as exc:
        raise UserFacingError("錯誤：執行時找不到 torch。") from exc

    model_inputs = tokenizer([prompt_text], return_tensors="pt").to(
        loaded_model.input_device
    )
    with torch.no_grad():
        generated_ids = model.generate(
            **model_inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
        )

    generated_ids = [
        output_ids[len(input_ids) :]
        for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
    ]
    response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
    return response


def contains_packaging_text(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    if "```" in normalized:
        return True
    lowered = normalized.lower()
    packaging_markers = (
        "以下是整理後的",
        "以下為整理後的",
        "以下是校正後的",
        "以下為校正後的",
        "這是整理後的",
        "這是校正後的",
        "希望這份",
        "如果你還需要",
        "markdown 內容如下",
    )
    return any(marker in normalized for marker in packaging_markers) or "as an ai" in lowered


def should_repair_output(draft: str) -> bool:
    if not draft:
        return True
    if contains_packaging_text(draft):
        return True
    if "\n---\n" in draft or draft.startswith("---") or draft.endswith("---"):
        return True
    paragraphs = [part.strip() for part in draft.split("\n\n") if part.strip()]
    if len(paragraphs) < 2 and len(draft) > 500:
        return True
    return False


def extract_number_tokens(text: str) -> List[str]:
    return re.findall(r"\d+(?:[./:-]\d+)*", text)


def extract_english_terms(text: str) -> List[str]:
    return re.findall(r"[A-Za-z][A-Za-z0-9._/-]*", text)


def missing_reference_numbers(reference_text: str, candidate_text: str) -> bool:
    candidate_numbers = set(extract_number_tokens(candidate_text))
    reference_numbers = set(extract_number_tokens(reference_text))
    return bool(reference_numbers and not reference_numbers.issubset(candidate_numbers))


def lost_too_many_english_terms(reference_text: str, candidate_text: str) -> bool:
    reference_terms = {term.lower() for term in extract_english_terms(reference_text)}
    if not reference_terms:
        return False
    candidate_lower = candidate_text.lower()
    retained = sum(1 for term in reference_terms if term in candidate_lower)
    if len(reference_terms) <= 2:
        return retained < len(reference_terms)
    return retained < max(1, len(reference_terms) // 2)


def is_abnormally_short(candidate_text: str, reference_text: str, ratio: float) -> bool:
    if len(reference_text) < 200:
        return False
    return len(candidate_text) < max(40, int(len(reference_text) * ratio))


def validate_repair_output(
    repaired_text: str, draft_text: str, original_content: str
) -> bool:
    if not repaired_text:
        return False
    if contains_packaging_text(repaired_text):
        return False
    if draft_text:
        if len(repaired_text) < max(20, int(len(draft_text) * REPAIR_MIN_RATIO)):
            return False
        if missing_reference_numbers(draft_text, repaired_text):
            return False
        if lost_too_many_english_terms(draft_text, repaired_text):
            return False
        return True

    if is_abnormally_short(repaired_text, original_content, SOURCE_MIN_RATIO):
        return False
    if missing_reference_numbers(original_content, repaired_text):
        return False
    if lost_too_many_english_terms(original_content, repaired_text):
        return False
    return True


def process_text(
    content: str,
    loaded_model: LoadedModel,
    style_guide: str,
    title_hint: str,
    prompt_config: PromptConfig,
    converter,
) -> str:
    initial_messages = build_messages(content, style_guide, title_hint, prompt_config)
    initial_prompt = render_prompt(loaded_model.tokenizer, initial_messages)
    ensure_prompt_within_budget(loaded_model, initial_prompt, "初稿 prompt")
    draft = generate_response(loaded_model, initial_prompt)
    if converter is not None:
        draft = converter.convert(draft)
    draft = clean_response(draft)

    if should_repair_output(draft):
        repair_messages = build_repair_messages(
            content, draft, style_guide, title_hint, prompt_config
        )
        repair_prompt = render_prompt(loaded_model.tokenizer, repair_messages)
        ensure_prompt_within_budget(loaded_model, repair_prompt, "repair prompt")
        repaired = generate_response(loaded_model, repair_prompt)
        if converter is not None:
            repaired = converter.convert(repaired)
        repaired = clean_response(repaired)
        if validate_repair_output(repaired, draft, content):
            draft = repaired

    if not draft:
        raise UserFacingError("錯誤：模型輸出為空。")
    final_output = clean_response(draft)
    if not final_output:
        raise UserFacingError("錯誤：模型輸出為空。")
    if is_abnormally_short(final_output, content, SOURCE_MIN_RATIO):
        raise UserFacingError("錯誤：模型輸出異常短，疑似截斷。")
    if contains_packaging_text(final_output):
        raise UserFacingError("錯誤：模型輸出包含與正文無關的包裝文字。")
    return final_output


def format_bool(value: bool) -> str:
    return "true" if value else "false"


def print_run_config(
    source_label: str,
    file_count: int,
    output_dir: Path,
    model_name: str,
    quantization: str,
    runtime_info: RuntimeInfo,
    replace_dict_path: Optional[str],
    style_guide_path: Optional[str],
    prompt_config_path: Optional[str],
    force: bool,
    device: str,
    dtype_name: str,
) -> None:
    print(f"[config] input={source_label}")
    print("[config] scan_depth=1")
    print("[config] file_types=.txt,.md")
    print(f"[config] files_found={file_count}")
    print(f"[config] output_dir={output_dir}")
    print(f"[config] model={model_name}")
    print(f"[config] quantization={quantization}")
    print(f"[config] device={device}")
    print(f"[config] dtype={dtype_name}")
    print(f"[config] cuda_available={format_bool(runtime_info.cuda_available)}")
    if runtime_info.gpu_name:
        print(f"[config] gpu={runtime_info.gpu_name}")
    print(f"[config] replace_dict={replace_dict_path or 'none'}")
    print(f"[config] style_guide={style_guide_path or 'none'}")
    print(f"[config] prompt_config={prompt_config_path or 'default'}")
    print(f"[config] force={format_bool(force)}")


def write_summary_files(
    output_dir: Path,
    source_label: str,
    files: Sequence[Path],
    args: argparse.Namespace,
    runtime_info: RuntimeInfo,
    device: str,
    dtype_name: str,
    model_memory_bytes: str,
    counts: Dict[str, int],
) -> None:
    now = datetime.now().astimezone()
    summary_lines = [
        f"timestamp={now.isoformat()}",
        f"cwd={Path.cwd()}",
        f"input={source_label}",
        "scan_depth=1",
        "file_types=.txt,.md",
        f"files_found={len(files)}",
        f"output_dir={output_dir}",
        f"model={args.model}",
        f"quantization={args.quantization}",
        f"device={device}",
        f"dtype={dtype_name}",
        f"model_memory_bytes={model_memory_bytes}",
        f"replace_dict={args.replace_dict or 'none'}",
        f"style_guide={args.style_guide or 'none'}",
        f"prompt_config={args.prompt_config or 'default'}",
        f"force={format_bool(args.force)}",
        f"success={counts['success']}",
        f"skipped={counts['skipped']}",
        f"failed={counts['failed']}",
    ]
    environment_lines = [
        f"timestamp={now.isoformat()}",
        f"cwd={Path.cwd()}",
        f"python_version={runtime_info.python_version}",
        f"torch_version={runtime_info.torch_version or 'missing'}",
        f"transformers_version={runtime_info.transformers_version or 'missing'}",
        f"accelerate_version={runtime_info.accelerate_version or 'missing'}",
        f"bitsandbytes_version={runtime_info.bitsandbytes_version or 'missing'}",
        f"cuda_available={format_bool(runtime_info.cuda_available)}",
        f"cuda_runtime={runtime_info.cuda_runtime or 'n/a'}",
        f"gpu_name={runtime_info.gpu_name or 'n/a'}",
        f"gpu_vram_mb={runtime_info.gpu_vram_mb or 'n/a'}",
        f"model={args.model}",
        f"quantization={args.quantization}",
        f"device={device}",
        f"dtype={dtype_name}",
        f"model_memory_bytes={model_memory_bytes}",
        f"prompt_config={args.prompt_config or 'default'}",
    ]
    if runtime_info.import_error:
        environment_lines.append(f"import_error={runtime_info.import_error}")

    (output_dir / "_run-summary.txt").write_text(
        "\n".join(summary_lines) + "\n", encoding="utf-8"
    )
    (output_dir / "_environment.txt").write_text(
        "\n".join(environment_lines) + "\n", encoding="utf-8"
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        runtime_info = detect_runtime_info()
        if args.check:
            load_prompt_config(args.prompt_config)
            if args.replace_dict:
                load_replace_dict(args.replace_dict)
            if args.style_guide:
                load_style_guide(args.style_guide)
            print("[check] transcript-polish 環境檢查")
            print(f"[check] python={runtime_info.python_version}")
            print(f"[check] torch={runtime_info.torch_version or 'missing'}")
            print(
                f"[check] transformers={runtime_info.transformers_version or 'missing'}"
            )
            print(f"[check] accelerate={runtime_info.accelerate_version or 'missing'}")
            print(
                f"[check] bitsandbytes={runtime_info.bitsandbytes_version or 'missing'}"
            )
            print(f"[check] cuda_available={format_bool(runtime_info.cuda_available)}")
            print(f"[check] model={args.model}")
            print(f"[check] quantization={args.quantization}")
            print("[check] 不會載入大型模型")
            return 0

        files, base_dir, source_label = resolve_input_files(args)
        if not files:
            raise UserFacingError(
                f"錯誤：找不到可處理檔案：{base_dir}（僅掃描第一層 .txt/.md）"
            )

        output_dir = resolve_output_dir(args, base_dir)
        external_replacements = load_replace_dict(args.replace_dict)
        style_guide = load_style_guide(args.style_guide)
        prompt_config = load_prompt_config(args.prompt_config)
        jobs = build_file_jobs(files, output_dir, args.force)
        converter = load_opencc_converter()
        output_dir.mkdir(parents=True, exist_ok=True)

        counts = {
            "success": 0,
            "skipped": sum(1 for job in jobs if job.skip),
            "failed": 0,
        }
        queued_jobs = [job for job in jobs if not job.skip]

        if not queued_jobs:
            print_run_config(
                source_label=source_label,
                file_count=len(files),
                output_dir=output_dir,
                model_name=args.model,
                quantization=args.quantization,
                runtime_info=runtime_info,
                replace_dict_path=args.replace_dict,
                style_guide_path=args.style_guide,
                prompt_config_path=args.prompt_config,
                force=args.force,
                device="not_loaded",
                dtype_name="not_loaded",
            )
            print(f"[run] queued={len(queued_jobs)}")
            for index, job in enumerate(jobs, 1):
                print(f"[{index}/{len(jobs)}] skipped -> {job.output_path}")
            write_summary_files(
                output_dir=output_dir,
                source_label=source_label,
                files=files,
                args=args,
                runtime_info=runtime_info,
                device="not_loaded",
                dtype_name="not_loaded",
                model_memory_bytes="not_loaded",
                counts=counts,
            )
            print(
                f"[summary] total={len(files)} success={counts['success']} "
                f"skipped={counts['skipped']} failed={counts['failed']}"
            )
            print(f"[summary] output_dir={output_dir}")
            return 0

        print(
            f"正在載入模型 {args.model}（quantization={args.quantization}）...",
            flush=True,
        )
        loaded_model = load_model(args.model, args.quantization)
        print("模型載入完成。", flush=True)

        print_run_config(
            source_label=source_label,
            file_count=len(files),
            output_dir=output_dir,
            model_name=args.model,
            quantization=loaded_model.quantization,
            runtime_info=runtime_info,
            replace_dict_path=args.replace_dict,
            style_guide_path=args.style_guide,
            prompt_config_path=args.prompt_config,
            force=args.force,
            device=loaded_model.device,
            dtype_name=loaded_model.dtype_name,
        )
        print(f"[run] queued={len(queued_jobs)}")

        for index, job in enumerate(jobs, 1):
            if job.skip:
                print(f"[{index}/{len(files)}] skipped -> {job.output_path}")
                continue

            print(f"[{index}/{len(files)}] processing {job.input_path.name}")
            try:
                raw_content = read_text_file(job.input_path)
                processed_input = normalize_transcript_text(raw_content, converter)
                processed_input = apply_replacements(processed_input, external_replacements)
                title_hint = derive_title_hint(job.input_path)
                result = process_text(
                    processed_input,
                    loaded_model,
                    style_guide,
                    title_hint,
                    prompt_config,
                    converter,
                )
                job.output_path.write_text(
                    result + ("\n" if result and not result.endswith("\n") else ""),
                    encoding="utf-8",
                )
                print(f"[{index}/{len(files)}] done -> {job.output_path}")
                counts["success"] += 1
            except Exception as exc:
                print(f"[{index}/{len(files)}] failed -> {job.input_path.name}: {exc}")
                counts["failed"] += 1

        write_summary_files(
            output_dir=output_dir,
            source_label=source_label,
            files=files,
            args=args,
            runtime_info=runtime_info,
            device=loaded_model.device,
            dtype_name=loaded_model.dtype_name,
            model_memory_bytes=loaded_model.model_memory_bytes,
            counts=counts,
        )

        print(
            f"[summary] total={len(files)} success={counts['success']} "
            f"skipped={counts['skipped']} failed={counts['failed']}"
        )
        print(f"[summary] output_dir={output_dir}")
        return 0 if counts["failed"] == 0 else 1
    except UserFacingError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
