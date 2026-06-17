import yaml
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from jinja2 import Template, Environment, FileSystemLoader


class TemplateManager:
    def __init__(self, templates_dir: Path):
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            keep_trailing_newline=True,
        )

    def list_templates(self) -> List[Dict[str, Any]]:
        templates = []
        if not self.templates_dir.exists():
            return templates
        
        for f in sorted(self.templates_dir.glob("**/*")):
            if f.is_file():
                rel_path = f.relative_to(self.templates_dir)
                templates.append({
                    "name": str(rel_path),
                    "path": str(f),
                    "format": self._detect_format(f.name),
                    "size": f.stat().st_size,
                })
        return templates

    def get_template(self, name: str) -> Optional[Dict[str, Any]]:
        template_path = self.templates_dir / name
        if not template_path.exists():
            return None
        return {
            "name": name,
            "path": str(template_path),
            "format": self._detect_format(template_path.name),
            "content": template_path.read_text(encoding="utf-8"),
        }

    def create_template(self, name: str, content: str = "", force: bool = False) -> Path:
        template_path = self.templates_dir / name
        if template_path.exists() and not force:
            raise FileExistsError(f"Template '{name}' already exists. Use --force to overwrite.")
        
        template_path.parent.mkdir(parents=True, exist_ok=True)
        template_path.write_text(content, encoding="utf-8")
        return template_path

    def render_template(self, name: str, variables: Dict[str, Any] = None) -> str:
        template_path = self.templates_dir / name
        if not template_path.exists():
            raise FileNotFoundError(f"Template '{name}' not found.")
        
        variables = variables or {}
        template = self._jinja_env.get_template(name)
        return template.render(**variables)

    def render_template_file(self, template_path: Path, variables: Dict[str, Any] = None) -> str:
        variables = variables or {}
        template = self._jinja_env.from_string(template_path.read_text(encoding="utf-8"))
        return template.render(**variables)

    def delete_template(self, name: str) -> bool:
        template_path = self.templates_dir / name
        if template_path.exists():
            template_path.unlink()
            return True
        return False

    def _detect_format(self, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        if ext in (".yaml", ".yml"):
            return "yaml"
        elif ext == ".json":
            return "json"
        elif ext in (".jinja", ".jinja2", ".j2"):
            return "jinja2"
        elif ext in (".env", ".conf", ".cfg", ".ini"):
            return ext[1:]
        else:
            return "text"


def load_yaml(file_path: Path) -> Dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_yaml(file_path: Path, data: Dict[str, Any]):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def load_json(file_path: Path) -> Dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(file_path: Path, data: Dict[str, Any]):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_config_file(file_path: Path) -> Dict[str, Any]:
    ext = file_path.suffix.lower()
    if ext in (".yaml", ".yml"):
        return load_yaml(file_path)
    elif ext == ".json":
        return load_json(file_path)
    else:
        raise ValueError(f"Unsupported config format: {ext}")


def save_config_file(file_path: Path, data: Dict[str, Any]):
    ext = file_path.suffix.lower()
    if ext in (".yaml", ".yml"):
        save_yaml(file_path, data)
    elif ext == ".json":
        save_json(file_path, data)
    else:
        raise ValueError(f"Unsupported config format: {ext}")
