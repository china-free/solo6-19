import sys
import json
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.tree import Tree

from . import __version__
from .config import get_config, ConfigForgeConfig
from .template import TemplateManager, load_config_file, save_config_file
from .environment import EnvironmentManager
from .crypto import (
    generate_master_key, encrypt_value, decrypt_value,
    encrypt_dict, decrypt_dict, get_master_key, is_encrypted
)
from .env_subst import load_env_file, substitute_env_variables
from .builder import ConfigBuilder
from .validator import ConfigValidator
from .git_integration import GitIntegration
from .deploy import DeployManager


console = Console()


class ConfigForgeCLI:
    def __init__(self):
        self.config = get_config()
        self.template_manager = TemplateManager(self.config.templates_dir)
        self.env_manager = EnvironmentManager(self.config.environments_dir)
        self.builder = ConfigBuilder(self.config)
        self.validator = ConfigValidator()
        self.git = GitIntegration(self.config.work_dir)
        self.deploy_manager = DeployManager(self.config.environments_dir / "deploy")


pass_cli = click.make_pass_decorator(ConfigForgeCLI, ensure=True)


@click.group()
@click.version_option(__version__, prog_name="configforge")
@click.option("--work-dir", type=click.Path(), help="工作目录")
@pass_cli
def cli(cli_obj, work_dir):
    """ConfigForge - 配置管理命令行工具
    
    管理配置模板、环境变量替换、加密敏感字段、多环境分发、
    Git集成追踪、配置校验、一键部署。
    """
    if work_dir:
        cli_obj.config.work_dir = Path(work_dir)
        cli_obj.config.ensure_dirs()


@cli.group()
def init():
    """初始化项目"""
    pass


@init.command("project")
@pass_cli
def init_project(cli_obj):
    """初始化配置项目目录结构"""
    cli_obj.config.ensure_dirs()
    
    configforge_file = cli_obj.config.work_dir / "configforge.yaml"
    if not configforge_file.exists():
        default_config = {
            "templates_dir": "templates",
            "environments_dir": "environments",
            "output_dir": "dist",
            "secrets_dir": ".secrets",
            "env_file": ".env",
        }
        save_config_file(configforge_file, default_config)
        console.print(f"[green]✓[/green] 创建配置文件: {configforge_file}")
    
    console.print(Panel.fit(
        f"[bold green]项目初始化完成![/bold green]\n\n"
        f"模板目录: {cli_obj.config.templates_dir}\n"
        f"环境目录: {cli_obj.config.environments_dir}\n"
        f"输出目录: {cli_obj.config.output_dir}\n"
        f"密钥目录: {cli_obj.config.secrets_dir}",
        title="ConfigForge"
    ))


@cli.group()
def template():
    """配置模板管理"""
    pass


@template.command("list")
@pass_cli
def template_list(cli_obj):
    """列出所有模板"""
    templates = cli_obj.template_manager.list_templates()
    
    if not templates:
        console.print("[yellow]未找到模板文件[/yellow]")
        return
    
    table = Table(title="配置模板", show_lines=True)
    table.add_column("名称", style="cyan")
    table.add_column("格式", style="green")
    table.add_column("大小", justify="right")
    table.add_column("路径", style="dim")
    
    for t in templates:
        table.add_row(
            t["name"],
            t["format"],
            f"{t['size']} B",
            t["path"],
        )
    
    console.print(table)


@template.command("show")
@click.argument("name")
@pass_cli
def template_show(cli_obj, name):
    """查看模板内容"""
    tpl = cli_obj.template_manager.get_template(name)
    if not tpl:
        console.print(f"[red]✗ 模板 '{name}' 不存在[/red]")
        sys.exit(1)
    
    syntax = Syntax(tpl["content"], tpl["format"], theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title=f"模板: {name}"))


@template.command("create")
@click.argument("name")
@click.option("--content", "-c", default="", help="模板内容")
@click.option("--from-file", "-f", type=click.Path(), help="从文件导入")
@click.option("--force", "-f", is_flag=True, help="强制覆盖")
@pass_cli
def template_create(cli_obj, name, content, from_file, force):
    """创建新模板"""
    if from_file:
        from_path = Path(from_file)
        if not from_path.exists():
            console.print(f"[red]✗ 文件不存在: {from_file}[/red]")
            sys.exit(1)
        content = from_path.read_text(encoding="utf-8")
    
    try:
        path = cli_obj.template_manager.create_template(name, content, force=force)
        console.print(f"[green]✓ 模板创建成功: {path}[/green]")
    except FileExistsError as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)


@template.command("delete")
@click.argument("name")
@click.option("--yes", "-y", is_flag=True, help="确认删除")
@pass_cli
def template_delete(cli_obj, name, yes):
    """删除模板"""
    if not yes:
        click.confirm(f"确定要删除模板 '{name}' 吗?", abort=True)
    
    if cli_obj.template_manager.delete_template(name):
        console.print(f"[green]✓ 模板已删除: {name}[/green]")
    else:
        console.print(f"[yellow]模板不存在: {name}[/yellow]")


@cli.group()
def env():
    """环境配置管理"""
    pass


@env.command("list")
@pass_cli
def env_list(cli_obj):
    """列出所有环境"""
    environments = cli_obj.env_manager.list_environments()
    
    if not environments:
        console.print("[yellow]未找到环境配置[/yellow]")
        return
    
    table = Table(title="环境列表")
    table.add_column("#", style="dim", justify="right")
    table.add_column("环境名称", style="cyan")
    
    for i, env_name in enumerate(environments, 1):
        table.add_row(str(i), env_name)
    
    console.print(table)


@env.command("show")
@click.argument("name")
@click.option("--decrypt", "-d", is_flag=True, help="解密敏感字段")
@pass_cli
def env_show(cli_obj, name, decrypt):
    """查看环境配置"""
    data = cli_obj.env_manager.get_environment(name)
    if data is None:
        console.print(f"[red]✗ 环境 '{name}' 不存在[/red]")
        sys.exit(1)
    
    if decrypt:
        try:
            master_key = get_master_key(cli_obj.config.master_key_env)
            data = decrypt_dict(data, master_key)
        except ValueError as e:
            console.print(f"[yellow]⚠ {e}[/yellow]")
    
    content = json.dumps(data, indent=2, ensure_ascii=False)
    syntax = Syntax(content, "json", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title=f"环境: {name}"))


@env.command("create")
@click.argument("name")
@click.option("--base", "-b", help="基于已有环境创建")
@click.option("--variable", "-v", multiple=True, help="设置变量 key=value")
@pass_cli
def env_create(cli_obj, name, base, variable):
    """创建新环境"""
    data = {}
    for var in variable:
        if "=" in var:
            k, v = var.split("=", 1)
            data[k.strip()] = v.strip()
    
    try:
        result = cli_obj.env_manager.create_environment(name, base_env=base, data=data if data else None)
        console.print(f"[green]✓ 环境创建成功: {name}[/green]")
        if base:
            console.print(f"  基于环境: {base}")
    except FileExistsError as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)


@env.command("set")
@click.argument("name")
@click.argument("key")
@click.argument("value")
@click.option("--encrypt", "-e", is_flag=True, help="加密该字段")
@pass_cli
def env_set(cli_obj, name, key, value, encrypt):
    """设置环境变量"""
    data = cli_obj.env_manager.get_environment(name)
    if data is None:
        console.print(f"[red]✗ 环境 '{name}' 不存在[/red]")
        sys.exit(1)
    
    if encrypt:
        try:
            master_key = get_master_key(cli_obj.config.master_key_env)
            value = encrypt_value(value, master_key)
        except ValueError as e:
            console.print(f"[red]✗ {e}[/red]")
            sys.exit(1)
    
    keys = key.split(".")
    current = data
    for k in keys[:-1]:
        if k not in current or not isinstance(current[k], dict):
            current[k] = {}
        current = current[k]
    current[keys[-1]] = value
    
    cli_obj.env_manager.save_environment(name, data)
    console.print(f"[green]✓ {key} = {value[:20] + '...' if len(value) > 20 else value}[/green]")


@env.command("delete")
@click.argument("name")
@click.option("--yes", "-y", is_flag=True, help="确认删除")
@pass_cli
def env_delete(cli_obj, name, yes):
    """删除环境"""
    if not yes:
        click.confirm(f"确定要删除环境 '{name}' 吗?", abort=True)
    
    if cli_obj.env_manager.delete_environment(name):
        console.print(f"[green]✓ 环境已删除: {name}[/green]")
    else:
        console.print(f"[yellow]环境不存在: {name}[/yellow]")


@env.command("diff")
@click.argument("env1")
@click.argument("env2")
@pass_cli
def env_diff(cli_obj, env1, env2):
    """比较两个环境的差异"""
    try:
        diffs = cli_obj.env_manager.compare_environments(env1, env2)
    except ValueError as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)
    
    console.print(f"[bold]比较 {env1} vs {env2}[/bold]\n")
    
    if diffs["only_in_first"]:
        console.print(f"[cyan]仅在 {env1} 中:[/cyan]")
        for k, v in diffs["only_in_first"].items():
            console.print(f"  + {k} = {v}")
        console.print()
    
    if diffs["only_in_second"]:
        console.print(f"[cyan]仅在 {env2} 中:[/cyan]")
        for k, v in diffs["only_in_second"].items():
            console.print(f"  + {k} = {v}")
        console.print()
    
    if diffs["different"]:
        console.print(f"[yellow]值不同的项:[/yellow]")
        for k, vals in diffs["different"].items():
            console.print(f"  ~ {k}:")
            console.print(f"    [{env1}] {vals[env1]}")
            console.print(f"    [{env2}] {vals[env2]}")
        console.print()
    
    if diffs["same"]:
        console.print(f"[green]相同的项 ({len(diffs['same'])}):[/green]")
        console.print(f"  {', '.join(diffs['same'].keys())}")


@cli.group()
def crypto():
    """加密解密功能"""
    pass


@crypto.command("gen-key")
def crypto_gen_key():
    """生成主密钥"""
    key = generate_master_key()
    console.print(Panel.fit(
        f"[bold green]主密钥生成成功![/bold green]\n\n"
        f"[cyan]{key}[/cyan]\n\n"
        f"[dim]请妥善保存此密钥，丢失将无法解密数据。[/dim]\n"
        f"[dim]设置环境变量: export CONFIGFORGE_MASTER_KEY='{key}'[/dim]",
        title="Master Key"
    ))


@crypto.command("encrypt")
@click.argument("value")
@pass_cli
def crypto_encrypt(cli_obj, value):
    """加密一个值"""
    try:
        master_key = get_master_key(cli_obj.config.master_key_env)
        encrypted = encrypt_value(value, master_key)
        console.print(f"[green]加密结果:[/green] {encrypted}")
    except ValueError as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)


@crypto.command("decrypt")
@click.argument("encrypted_value")
@pass_cli
def crypto_decrypt(cli_obj, encrypted_value):
    """解密一个值"""
    try:
        master_key = get_master_key(cli_obj.config.master_key_env)
        decrypted = decrypt_value(encrypted_value, master_key)
        console.print(f"[green]解密结果:[/green] {decrypted}")
    except ValueError as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ 解密失败: {e}[/red]")
        sys.exit(1)


@crypto.command("encrypt-file")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--output", "-o", help="输出文件路径")
@pass_cli
def crypto_encrypt_file(cli_obj, file_path, output):
    """加密配置文件中的敏感字段"""
    try:
        master_key = get_master_key(cli_obj.config.master_key_env)
        data = load_config_file(Path(file_path))
        encrypted = encrypt_dict(data, master_key)
        
        output_path = Path(output) if output else Path(file_path)
        save_config_file(output_path, encrypted)
        console.print(f"[green]✓ 敏感字段已加密: {output_path}[/green]")
    except ValueError as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)


@crypto.command("decrypt-file")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--output", "-o", help="输出文件路径")
@pass_cli
def crypto_decrypt_file(cli_obj, file_path, output):
    """解密配置文件中的加密字段"""
    try:
        master_key = get_master_key(cli_obj.config.master_key_env)
        data = load_config_file(Path(file_path))
        decrypted = decrypt_dict(data, master_key)
        
        output_path = Path(output) if output else Path(file_path)
        save_config_file(output_path, decrypted)
        console.print(f"[green]✓ 字段已解密: {output_path}[/green]")
    except ValueError as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)


@cli.group()
def build():
    """构建配置文件"""
    pass


@build.command("one")
@click.argument("template")
@click.argument("environment")
@click.option("--output", "-o", help="输出文件名")
@click.option("--decrypt", "-d", is_flag=True, help="输出解密后的配置")
@click.option("--no-encrypt", is_flag=True, help="不加密输出")
@pass_cli
def build_one(cli_obj, template, environment, output, decrypt, no_encrypt):
    """构建单个环境的配置"""
    try:
        result_path = cli_obj.builder.build_and_save(
            template_name=template,
            env_name=environment,
            output_name=output,
            decrypt=decrypt,
            encrypt=not no_encrypt and not decrypt,
        )
        console.print(f"[green]✓ 配置构建成功: {result_path}[/green]")
    except Exception as e:
        console.print(f"[red]✗ 构建失败: {e}[/red]")
        sys.exit(1)


@build.command("all")
@click.option("--template", "-t", help="指定模板（默认全部）")
@click.option("--decrypt", "-d", is_flag=True, help="输出解密后的配置")
@click.option("--no-encrypt", is_flag=True, help="不加密输出")
@pass_cli
def build_all(cli_obj, template, decrypt, no_encrypt):
    """构建所有环境的配置"""
    results = cli_obj.builder.build_all(
        template_name=template,
        decrypt=decrypt,
        encrypt=not no_encrypt and not decrypt,
    )
    
    for env_name, files in results.items():
        console.print(f"\n[bold cyan]环境: {env_name}[/bold cyan]")
        for f in files:
            if isinstance(f, Path):
                console.print(f"  [green]✓[/green] {f}")
            else:
                console.print(f"  [red]✗ {f}[/red]")


@build.command("diff")
@click.argument("template")
@click.argument("env1")
@click.argument("env2")
@pass_cli
def build_diff(cli_obj, template, env1, env2):
    """比较两个环境构建后的配置差异"""
    try:
        diffs = cli_obj.builder.diff_envs(template, env1, env2)
    except Exception as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)
    
    console.print(f"[bold]模板 {template} - {env1} vs {env2}[/bold]\n")
    
    if diffs["only_in_first"]:
        console.print(f"[cyan]仅在 {env1} 中:[/cyan]")
        for k, v in diffs["only_in_first"].items():
            console.print(f"  + {k} = {v}")
        console.print()
    
    if diffs["only_in_second"]:
        console.print(f"[cyan]仅在 {env2} 中:[/cyan]")
        for k, v in diffs["only_in_second"].items():
            console.print(f"  + {k} = {v}")
        console.print()
    
    if diffs["different"]:
        console.print(f"[yellow]值不同的项:[/yellow]")
        for k, vals in diffs["different"].items():
            console.print(f"  ~ {k}:")
            console.print(f"    [{env1}] {vals[env1]}")
            console.print(f"    [{env2}] {vals[env2]}")


@cli.group()
def validate():
    """配置校验"""
    pass


@validate.command("config")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--schema", "-s", type=click.Path(), help="JSON Schema 文件")
@click.option("--required", "-r", multiple=True, help="必需字段")
@click.option("--no-secret-check", is_flag=True, help="不检查明文密钥")
@pass_cli
def validate_config(cli_obj, file_path, schema, required, no_secret_check):
    """校验配置文件"""
    data = load_config_file(Path(file_path))
    
    schema_path = Path(schema) if schema else None
    required_fields = list(required) if required else None
    
    result = cli_obj.validator.comprehensive_validate(
        data,
        schema_path=schema_path,
        required_fields=required_fields,
        check_secrets=not no_secret_check,
    )
    
    if result["valid"]:
        console.print(f"[green]✓ 配置校验通过[/green]")
    else:
        console.print(f"[red]✗ 配置校验失败[/red]")
        for err in result["errors"]:
            console.print(f"  [red]- {err}[/red]")
    
    if result["warnings"]:
        console.print(f"\n[yellow]警告 ({len(result['warnings'])}):[/yellow]")
        for warn in result["warnings"]:
            console.print(f"  [yellow]! {warn}[/yellow]")
    
    if not result["valid"]:
        sys.exit(1)


@cli.group()
def git():
    """Git 集成"""
    pass


@git.command("status")
@pass_cli
def git_status(cli_obj):
    """查看 Git 状态"""
    if not cli_obj.git.is_available():
        console.print("[yellow]Git 仓库不可用[/yellow]")
        return
    
    status = cli_obj.git.status()
    if "error" in status:
        console.print(f"[red]✗ {status['error']}[/red]")
        return
    
    table = Table(title="Git 状态")
    table.add_column("属性", style="cyan")
    table.add_column("值")
    
    table.add_row("分支", status["branch"])
    table.add_row("提交", status.get("commit", "N/A")[:7] if status.get("commit") else "N/A")
    table.add_row("状态", "[green]clean[/green]" if not status["dirty"] else "[yellow]dirty[/yellow]")
    
    console.print(table)
    
    if status.get("untracked"):
        console.print(f"\n[yellow]未跟踪文件 ({len(status['untracked'])}):[/yellow]")
        for f in status["untracked"]:
            console.print(f"  ? {f}")
    
    if status.get("modified"):
        console.print(f"\n[cyan]已修改文件 ({len(status['modified'])}):[/cyan]")
        for f in status["modified"]:
            console.print(f"  M {f}")


@git.command("commit")
@click.argument("message")
@click.option("--files", "-f", multiple=True, help="指定提交的文件")
@click.option("--author", "-a", help="提交者")
@pass_cli
def git_commit(cli_obj, message, files, author):
    """提交配置变更"""
    if not cli_obj.git.is_available():
        console.print("[red]✗ Git 仓库不可用[/red]")
        sys.exit(1)
    
    try:
        commit_hash = cli_obj.git.commit_configs(
            message=message,
            files=list(files) if files else None,
            author=author,
        )
        if commit_hash:
            console.print(f"[green]✓ 提交成功: {commit_hash[:7]}[/green]")
        else:
            console.print("[yellow]没有可提交的内容[/yellow]")
    except RuntimeError as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)


@git.command("history")
@click.option("--file", "-f", help="指定文件历史")
@click.option("--limit", "-n", default=20, help="显示条数")
@pass_cli
def git_history(cli_obj, file, limit):
    """查看提交历史"""
    if not cli_obj.git.is_available():
        console.print("[yellow]Git 仓库不可用[/yellow]")
        return
    
    history = cli_obj.git.get_history(file_path=file, limit=limit)
    
    if not history:
        console.print("[yellow]没有提交记录[/yellow]")
        return
    
    table = Table(title="提交历史")
    table.add_column("提交", style="cyan")
    table.add_column("作者", style="green")
    table.add_column("日期", style="yellow")
    table.add_column("信息")
    
    for commit in history:
        table.add_row(
            commit["short_hash"],
            commit["author"],
            commit["date"].strftime("%Y-%m-%d %H:%M"),
            commit["summary"],
        )
    
    console.print(table)


@git.command("init")
@pass_cli
def git_init(cli_obj):
    """初始化 Git 仓库"""
    if cli_obj.git.is_available():
        console.print("[yellow]Git 仓库已存在[/yellow]")
        return
    
    if cli_obj.git.init_repo():
        console.print("[green]✓ Git 仓库初始化成功[/green]")
    else:
        console.print("[red]✗ Git 仓库初始化失败[/red]")
        sys.exit(1)


@cli.group()
def deploy():
    """部署配置"""
    pass


@deploy.command("list")
@pass_cli
def deploy_list(cli_obj):
    """列出部署目标"""
    targets = cli_obj.deploy_manager.list_targets()
    
    if not targets:
        console.print("[yellow]未找到部署目标配置[/yellow]")
        return
    
    table = Table(title="部署目标")
    table.add_column("#", style="dim", justify="right")
    table.add_column("目标名称", style="cyan")
    
    for i, target in enumerate(targets, 1):
        table.add_row(str(i), target)
    
    console.print(table)


@deploy.command("run")
@click.argument("target")
@click.option("--env", "-e", required=True, help="环境名称")
@click.option("--dry-run", "-n", is_flag=True, help="试运行")
@click.option("--decrypt", "-d", is_flag=True, help="部署解密后的配置")
@pass_cli
def deploy_run(cli_obj, target, env, dry_run, decrypt):
    """部署配置到目标服务器"""
    deploy_target = cli_obj.deploy_manager.load_target(target)
    if not deploy_target:
        console.print(f"[red]✗ 部署目标 '{target}' 不存在[/red]")
        sys.exit(1)
    
    templates = cli_obj.template_manager.list_templates()
    local_files = {}
    
    for tpl in templates:
        try:
            result_path = cli_obj.builder.build_and_save(
                template_name=tpl["name"],
                env_name=env,
                decrypt=decrypt,
                encrypt=not decrypt,
            )
            local_files[tpl["name"]] = result_path
        except Exception as e:
            console.print(f"[yellow]⚠ 构建 {tpl['name']} 失败: {e}[/yellow]")
    
    if not local_files:
        console.print("[red]✗ 没有可部署的文件[/red]")
        sys.exit(1)
    
    result = cli_obj.deploy_manager.deploy_files(
        deploy_target,
        local_files,
        dry_run=dry_run,
    )
    
    if result["success"]:
        console.print(f"[green]✓ 部署成功[/green]")
    else:
        console.print(f"[red]✗ 部署失败[/red]")
    
    if result["output"]:
        console.print("\n[cyan]输出:[/cyan]")
        for line in result["output"]:
            console.print(f"  {line}")
    
    if result["errors"]:
        console.print("\n[red]错误:[/red]")
        for err in result["errors"]:
            console.print(f"  {err}")
    
    if not result["success"]:
        sys.exit(1)


def main():
    cli()


if __name__ == "__main__":
    main()
