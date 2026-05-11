from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PromptAsset:
    prompt_id: str
    version: str
    path: Path
    content: str


class PromptRegistry:
    def __init__(self, prompts_path: Path) -> None:
        self.prompts_path = prompts_path

    def load(self, prompt_id: str, version: str) -> PromptAsset:
        path = self.prompts_path / f"{prompt_id}.v{version}.md"
        if not path.exists():
            raise FileNotFoundError(f"Prompt asset {path} was not found")
        return PromptAsset(
            prompt_id=prompt_id,
            version=version,
            path=path,
            content=path.read_text(encoding="utf-8"),
        )
