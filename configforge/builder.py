import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from copy import deepcopy

from .config import ConfigForgeConfig
from .template import TemplateManager, load_config_file, save_config_file
from .environment import EnvironmentManager, deep_merge
from .env_subst import substitute_env_in_dict, load_env_file
from .crypto import encrypt_dict, decrypt_dict, get_master_key, is_encrypted


class ConfigBuilder:
    def __init__(self, config: ConfigForgeConfig):
        self.config = config
        self.template_manager = TemplateManager(config.templates_dir)
        self.env_manager = EnvironmentManager(config.environments_dir)

    def build(
        self,
        template_name: str,
        env_name: str,
        output_format: str = None,
        decrypt: bool = False,
        encrypt: bool = True,
        extra_vars: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        template_data = self._load_template_data(template_name)
        env_data = self.env_manager.get_environment(env_name)
        
        if env_data is None:
            raise ValueError(f"Environment '{env_name}' not found.")

        merged = deep_merge(template_data, env_data)
        
        if extra_vars:
            merged = deep_merge(merged, extra_vars)

        env_vars = load_env_file(self.config.env_file)
        merged = substitute_env_in_dict(merged, env_vars)

        if decrypt:
            master_key = get_master_key(self.config.master_key_env)
            merged = decrypt_dict(merged, master_key)
        elif encrypt:
            master_key = get_master_key(self.config.master_key_env)
            merged = encrypt_dict(merged, master_key)

        return merged

    def build_and_save(
        self,
        template_name: str,
        env_name: str,
        output_name: str = None,
        output_format: str = None,
        decrypt: bool = False,
        encrypt: bool = True,
    ) -> Path:
        data = self.build(
            template_name=template_name,
            env_name=env_name,
            output_format=output_format,
            decrypt=decrypt,
            encrypt=encrypt,
        )

        if not output_name:
            stem = Path(template_name).stem
            output_name = f"{stem}.{env_name}.yaml"

        output_path = self.config.output_dir / env_name / output_name
        
        if output_format:
            output_path = output_path.with_suffix(f".{output_format}")

        save_config_file(output_path, data)
        return output_path

    def build_all(
        self,
        template_name: str = None,
        decrypt: bool = False,
        encrypt: bool = True,
    ) -> Dict[str, List[Path]]:
        results = {}
        environments = self.env_manager.list_environments()
        
        templates = [template_name] if template_name else [
            t["name"] for t in self.template_manager.list_templates()
        ]

        for env in environments:
            results[env] = []
            for tpl in templates:
                try:
                    path = self.build_and_save(
                        template_name=tpl,
                        env_name=env,
                        decrypt=decrypt,
                        encrypt=encrypt,
                    )
                    results[env].append(path)
                except Exception as e:
                    results[env].append(f"ERROR: {e}")

        return results

    def diff_envs(
        self,
        template_name: str,
        env1: str,
        env2: str,
    ) -> Dict[str, Any]:
        data1 = self.build(template_name, env1, encrypt=False)
        data2 = self.build(template_name, env2, encrypt=False)

        diffs = {
            "template": template_name,
            "env1": env1,
            "env2": env2,
            "only_in_first": {},
            "only_in_second": {},
            "different": {},
            "same": {},
        }

        all_keys = set(data1.keys()) | set(data2.keys())

        for key in sorted(all_keys):
            if key not in data2:
                diffs["only_in_first"][key] = data1[key]
            elif key not in data1:
                diffs["only_in_second"][key] = data2[key]
            elif data1[key] != data2[key]:
                diffs["different"][key] = {
                    env1: data1[key],
                    env2: data2[key],
                }
            else:
                diffs["same"][key] = data1[key]

        return diffs

    def _load_template_data(self, template_name: str) -> Dict[str, Any]:
        template_info = self.template_manager.get_template(template_name)
        if not template_info:
            raise FileNotFoundError(f"Template '{template_name}' not found.")
        
        template_path = Path(template_info["path"])
        ext = template_path.suffix.lower()
        
        if ext in (".yaml", ".yml", ".json"):
            return load_config_file(template_path)
        elif ext in (".jinja", ".jinja2", ".j2"):
            rendered = self.template_manager.render_template(template_name)
            inner_ext = Path(template_name).stem
            if inner_ext.endswith((".yaml", ".yml")):
                return yaml.safe_load(rendered) or {}
            elif inner_ext.endswith(".json"):
                import json
                return json.loads(rendered)
            else:
                return {"content": rendered}
        else:
            return {"content": template_info["content"]}
