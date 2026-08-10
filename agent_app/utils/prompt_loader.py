from pathlib import Path


PROMPT_DIR = Path(__file__).parent.parent / "prompts"
SKILL_DIR = Path(__file__).parent.parent / "skills"


def load_prompt(name: str, **kwargs) -> str:

    prompt = (
        Path(PROMPT_DIR)
        .joinpath(name)
        .read_text(
            encoding="utf-8"
        )
    )

    for k, v in kwargs.items():
        prompt = prompt.replace(
            "{{" + k + "}}",
            str(v),
        )

    return prompt

def load_skill(name: str) -> str:
    path = SKILL_DIR / name
    with open(path, "r", encoding="utf-8") as f:
        return f.read()