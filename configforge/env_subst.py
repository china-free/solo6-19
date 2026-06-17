import os
import re
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv


BRACED_PATTERN = re.compile(r'\$\{([A-Za-z_][A-Za-z0-9_]*):([^}]*)\}')
BARE_PATTERN = re.compile(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}')
SIMPLE_PATTERN = re.compile(r'\$([A-Za-z_][A-Za-z0-9_]*)')


def load_env_file(env_file: str = ".env") -> Dict[str, str]:
    env_vars = {}
    env_path = Path(env_file)
    if env_path.exists():
        load_dotenv(env_path)
    
    for key, value in os.environ.items():
        env_vars[key] = value
    
    return env_vars


def substitute_env_variables(content: str, env_vars: Dict[str, str] = None) -> str:
    if env_vars is None:
        env_vars = load_env_file()
    
    def replace_braced_default(match):
        var_name = match.group(1)
        default = match.group(2)
        return env_vars.get(var_name, default)
    
    def replace_braced(match):
        var_name = match.group(1)
        if var_name in env_vars:
            return env_vars[var_name]
        return match.group(0)
    
    def replace_simple(match):
        var_name = match.group(1)
        if var_name in env_vars:
            return env_vars[var_name]
        return match.group(0)
    
    content = BRACED_PATTERN.sub(replace_braced_default, content)
    content = BARE_PATTERN.sub(replace_braced, content)
    content = SIMPLE_PATTERN.sub(replace_simple, content)
    
    return content


def substitute_env_in_dict(data: Dict[str, Any], env_vars: Dict[str, str] = None) -> Dict[str, Any]:
    if env_vars is None:
        env_vars = load_env_file()
    
    def _substitute(obj):
        if isinstance(obj, dict):
            return {k: _substitute(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_substitute(item) for item in obj]
        elif isinstance(obj, str):
            return substitute_env_variables(obj, env_vars)
        else:
            return obj
    
    return _substitute(data)


def get_env_var(name: str, default: str = None, env_file: str = ".env") -> Optional[str]:
    env_vars = load_env_file(env_file)
    return env_vars.get(name, default)


def has_env_vars(content: str) -> bool:
    return bool(
        BRACED_PATTERN.search(content)
        or BARE_PATTERN.search(content)
        or SIMPLE_PATTERN.search(content)
    )
