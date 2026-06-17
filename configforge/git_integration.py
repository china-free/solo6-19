from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    import git
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False


class GitIntegration:
    def __init__(self, repo_path: Path):
        self.repo_path = Path(repo_path)
        self._repo = None
        if GIT_AVAILABLE and self._is_git_repo():
            self._repo = git.Repo(str(self.repo_path))

    def _is_git_repo(self) -> bool:
        try:
            git.Repo(str(self.repo_path))
            return True
        except Exception:
            return False

    def is_available(self) -> bool:
        return self._repo is not None

    def init_repo(self) -> bool:
        if self._is_git_repo():
            return False
        if GIT_AVAILABLE:
            self._repo = git.Repo.init(str(self.repo_path))
            return True
        return False

    def status(self) -> Dict[str, Any]:
        if not self.is_available():
            return {"error": "Git repository not available"}
        
        try:
            repo = self._repo
            return {
                "branch": repo.active_branch.name if not repo.head.is_detached else "detached",
                "commit": repo.head.commit.hexsha if repo.head.is_valid() else None,
                "dirty": repo.is_dirty(untracked_files=True),
                "untracked": repo.untracked_files,
                "modified": [item.a_path for item in repo.index.diff(None)],
                "staged": [item.a_path for item in repo.index.diff("HEAD")] if repo.head.is_valid() else [],
            }
        except Exception as e:
            return {"error": str(e)}

    def commit_configs(
        self,
        message: str,
        files: List[str] = None,
        author: str = None,
    ) -> Optional[str]:
        if not self.is_available():
            return None
        
        try:
            repo = self._repo
            
            if files:
                repo.index.add(files)
            else:
                repo.index.add("*")
            
            commit_kwargs = {"message": message}
            if author:
                commit_kwargs["author"] = git.Actor(author, f"{author}@configforge.local")
            
            commit = repo.index.commit(**commit_kwargs)
            return commit.hexsha
        except Exception as e:
            raise RuntimeError(f"Git commit failed: {e}")

    def get_history(self, file_path: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        if not self.is_available():
            return []
        
        try:
            repo = self._repo
            commits = []
            
            kwargs = {"max_count": limit}
            if file_path:
                kwargs["paths"] = file_path
            
            for commit in repo.iter_commits(**kwargs):
                commits.append({
                    "hash": commit.hexsha,
                    "short_hash": commit.hexsha[:7],
                    "author": commit.author.name if commit.author else "unknown",
                    "email": commit.author.email if commit.author else "",
                    "date": datetime.fromtimestamp(commit.committed_date),
                    "message": commit.message.strip(),
                    "summary": commit.summary,
                })
            return commits
        except Exception as e:
            return []

    def show_diff(self, file_path: str = None, staged: bool = False) -> str:
        if not self.is_available():
            return ""
        
        try:
            repo = self._repo
            if staged:
                diff = repo.index.diff("HEAD")
            else:
                diff = repo.index.diff(None)
            
            if file_path:
                diff = [d for d in diff if d.a_path == file_path or d.b_path == file_path]
            
            result = []
            for d in diff:
                result.append(f"--- {d.a_path}")
                result.append(f"+++ {d.b_path}")
                if d.diff:
                    result.append(d.diff.decode("utf-8", errors="replace"))
            return "\n".join(result)
        except Exception as e:
            return f"Error: {e}"

    def get_file_content_at_commit(self, file_path: str, commit_hash: str) -> Optional[str]:
        if not self.is_available():
            return None
        
        try:
            repo = self._repo
            commit = repo.commit(commit_hash)
            blob = commit.tree / file_path
            return blob.data_stream.read().decode("utf-8", errors="replace")
        except Exception:
            return None

    def create_tag(self, tag_name: str, message: str = None) -> bool:
        if not self.is_available():
            return False
        
        try:
            self._repo.create_tag(tag_name, message=message or f"Tag {tag_name}")
            return True
        except Exception:
            return False

    def list_tags(self) -> List[str]:
        if not self.is_available():
            return []
        
        try:
            return [tag.name for tag in sorted(self._repo.tags, key=lambda t: t.commit.committed_date, reverse=True)]
        except Exception:
            return []
