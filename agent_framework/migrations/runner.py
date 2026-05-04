"""Migration Runner — 数据库迁移执行器。

职责：
- 自动检测并执行所有尚未运行的迁移脚本
- 记录已执行迁移（防止重复执行）
- 支持回滚（down）操作
- 迁移事务包装

PRD 引用：prd/schema/database.md
"""

import sqlite3
import time
from pathlib import Path
from typing import List, Optional, Tuple


class MigrationRunner:
    """数据库迁移执行器。

    用法：
        runner = MigrationRunner("~/.suri/runtime/suri.db", "agent_framework/migrations")
        runner.run_all()
    """

    def __init__(self, db_path: str, migrations_dir: str):
        self._db_path = Path(db_path).expanduser()
        self._migrations_dir = Path(migrations_dir)
        self._ensure_meta_table()

    def _ensure_meta_table(self) -> None:
        """确保 migrations 元数据表存在。"""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                name TEXT,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                checksum TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接。"""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def get_applied_versions(self) -> List[str]:
        """获取已执行的迁移版本号列表。"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT version FROM schema_migrations ORDER BY version ASC"
        ).fetchall()
        conn.close()
        return [r["version"] for r in rows]

    def get_pending_migrations(self) -> List[Path]:
        """获取待执行的迁移脚本（按文件名排序）。"""
        if not self._migrations_dir.exists():
            return []

        applied = set(self.get_applied_versions())
        pending = []
        for f in sorted(self._migrations_dir.glob("*.sql")):
            version = f.stem.split("_", 1)[0] if "_" in f.stem else f.stem
            if version not in applied:
                pending.append(f)
        return pending

    def run_all(self, dry_run: bool = False) -> List[dict]:
        """执行所有待执行的迁移。

        Args:
            dry_run: True 时仅打印，不实际执行

        Returns:
            执行结果列表：[{version, name, status, error}]
        """
        pending = self.get_pending_migrations()
        if not pending:
            print("[MigrationRunner] ✅ 所有迁移已执行，无需操作")
            return []

        results = []
        for migration_file in pending:
            result = self._run_migration(migration_file, dry_run)
            results.append(result)

        return results

    def _run_migration(self, file_path: Path, dry_run: bool = False) -> dict:
        """执行单个迁移脚本。"""
        version = file_path.stem.split("_", 1)[0] if "_" in file_path.stem else file_path.stem
        name = file_path.stem

        print(f"[MigrationRunner] {'[DRY RUN] ' if dry_run else ''}执行迁移: {name}")

        try:
            sql = file_path.read_text(encoding="utf-8")

            if dry_run:
                print(f"  SQL: {sql[:200]}...")
                return {"version": version, "name": name, "status": "dry_run"}

            # 在事务中执行
            conn = self._get_conn()
            try:
                conn.execute("BEGIN TRANSACTION")
                conn.executescript(sql)
                conn.execute("""
                    INSERT INTO schema_migrations (version, name, checksum)
                    VALUES (?, ?, ?)
                """, (version, name, str(hash(sql))))
                conn.commit()
                print(f"  ✅ 迁移 {name} 执行成功")
                status = "success"
            except Exception as e:
                conn.rollback()
                print(f"  ❌ 迁移 {name} 执行失败: {e}")
                status = "failed"
            finally:
                conn.close()

            return {"version": version, "name": name, "status": status}

        except Exception as e:
            return {"version": version, "name": name, "status": "error", "error": str(e)}

    def rollback(self, version: str = "") -> bool:
        """回滚迁移（反向执行 SQL 中的 -- DOWN 部分）。

        注意：需要迁移文件包含 -- DOWN 注释标记。
        SQLite 不支持完整的 DDL 回滚，此操作仅执行 DOWN 块。
        """
        if version:
            # 回滚到指定版本（之后的所有迁移回滚）
            target = version
            applied = self.get_applied_versions()
            to_rollback = [v for v in reversed(applied) if v > target]
        else:
            # 回滚最后一个迁移
            applied = self.get_applied_versions()
            to_rollback = [applied[-1]] if applied else []

        if not to_rollback:
            print("[MigrationRunner] ⚠️ 没有可回滚的迁移")
            return False

        for ver in to_rollback:
            # 查找迁移文件
            migration_file = None
            for f in self._migrations_dir.glob(f"{ver}_*.sql"):
                migration_file = f
                break
            if not migration_file:
                print(f"[MigrationRunner] ⚠️ 未找到迁移文件: {ver}")
                continue

            # 提取 DOWN 部分
            sql = migration_file.read_text(encoding="utf-8")
            if "-- DOWN" not in sql:
                print(f"[MigrationRunner] ⚠️ 迁移 {ver} 没有 DOWN 块，跳过回滚")
                continue

            down_sql = sql.split("-- DOWN", 1)[1].strip()
            if not down_sql:
                continue

            conn = self._get_conn()
            try:
                conn.execute("BEGIN TRANSACTION")
                conn.executescript(down_sql)
                conn.execute("DELETE FROM schema_migrations WHERE version = ?", (ver,))
                conn.commit()
                print(f"[MigrationRunner] ✅ 已回滚迁移: {ver}")
            except Exception as e:
                conn.rollback()
                print(f"[MigrationRunner] ❌ 回滚失败: {e}")
                return False
            finally:
                conn.close()

        return True

    def status(self) -> List[dict]:
        """查看迁移状态。"""
        applied = set(self.get_applied_versions())
        all_migrations = sorted(self._migrations_dir.glob("*.sql")) if self._migrations_dir.exists() else []

        result = []
        for f in all_migrations:
            version = f.stem.split("_", 1)[0] if "_" in f.stem else f.stem
            result.append({
                "version": version,
                "name": f.stem,
                "applied": version in applied,
            })
        return result