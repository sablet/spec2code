"""Integrity検証エンジン

仕様（SpecIR）と実装の整合性を検証する。
Check/Transform/Generator関数の存在、位置、シグネチャを検証する。
"""

from __future__ import annotations

import importlib
import inspect
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from spectool.spectool.core.base.ir import CheckSpec, GeneratorDef, SpecIR, TransformSpec


class IntegrityValidator:
    """Integrity検証クラス

    SpecIRと実装の整合性を検証する。
    Check/Transform/Generator関数の存在、位置、シグネチャを検証する。
    """

    def __init__(self, ir: SpecIR):
        """初期化

        Args:
            ir: SpecIR（中間表現）
        """
        self.ir = ir

    def _resolve_impl_path(self, impl: str, file_path: str | None = None) -> str:
        """implパスを解決（apps. プレフィックスをプロジェクト名を含む形に変換）

        Args:
            impl: 元のimplパス (例: "apps.checks:func" または "apps.project_name.checks:func")
            file_path: ファイルパス（短縮形式の場合に完全なモジュールパスを推測するために使用）

        Returns:
            解決されたimplパス (例: "apps.sample-project.checks:func")
        """
        if not impl.startswith("apps."):
            return impl

        # プロジェクト名を取得
        app_name = self.ir.meta.name if self.ir.meta else "app"

        # "apps." の後の部分を取得
        rest = impl[5:]  # "apps." を除去

        # 既にプロジェクト名が含まれているかチェック
        # rest が "{app_name}." で始まっていたら、既に正しい形式なのでそのまま返す
        if rest.startswith(f"{app_name}."):
            return impl

        # 短縮形式の場合、file_pathから完全なモジュールパスを推測
        if file_path and ":" in impl:
            func_name = impl.split(":", 1)[1]
            module_path = self._infer_module_path_from_file(file_path)
            return f"{module_path}:{func_name}"

        # file_pathが無い場合は、プロジェクト名を挿入
        # "apps.<project-name>." + 残りの部分
        return f"apps.{app_name}.{rest}"

    def _infer_module_path_from_file(self, file_path: str) -> str:
        """file_pathから完全なモジュールパスを推測

        Args:
            file_path: ファイルパス（例: "checks/validators.py" または "apps/checks/validators.py"）

        Returns:
            モジュールパス（例: "apps.test_project.checks.validators"）
        """
        app_name = self.ir.meta.name if self.ir.meta else "app"

        # Pathオブジェクトに変換
        path = Path(file_path)

        # "apps" プレフィックスを除去
        if path.parts and path.parts[0] == "apps":
            path = Path(*path.parts[1:])

        # .pyを除去してモジュールパスに変換
        module_parts = list(path.with_suffix("").parts)

        # apps.<app_name>.<module_path>の形式で返す
        return f"apps.{app_name}.{'.'.join(module_parts)}"

    def validate_integrity(self, project_root: Path) -> dict[str, list[str]]:
        """完全なIntegrity検証

        Args:
            project_root: プロジェクトルートディレクトリ

        Returns:
            エラーマップ {category: [error_messages]}
        """
        print("🔍 Validating spec-implementation integrity...")
        errors: dict[str, list[str]] = {
            "check_functions": [],
            "check_locations": [],
            "transform_functions": [],
            "transform_signatures": [],
            "transform_locations": [],
            "transform_annotations": [],
            "generator_functions": [],
            "generator_locations": [],
            "generator_signatures": [],
        }

        # sys.pathにプロジェクトルートを追加（apps.XXX形式のimportのため）
        project_root_str = str(project_root.resolve())
        if project_root_str not in sys.path:
            sys.path.insert(0, project_root_str)

        # モジュールキャッシュをクリア（テスト環境で重要）
        self._clear_module_cache()

        # Check関数の検証
        self._validate_checks(project_root, errors)

        # Transform関数の検証
        self._validate_transforms(project_root, errors)

        # Generator関数の検証
        self._validate_generators(project_root, errors)

        # サマリー表示
        self._summarize_integrity(errors)

        return errors

    def _validate_checks(self, project_root: Path, errors: dict[str, list[str]]) -> None:
        """Check関数の存在と位置を検証

        Args:
            project_root: プロジェクトルートディレクトリ
            errors: エラーマップ
        """
        if not self.ir.checks:
            return

        print("\n📋 Validating Check functions:")
        print("=" * 80)

        for check in self.ir.checks:
            self._validate_single_check(check, project_root, errors)

        print("=" * 80)

    def _resolve_file_path(self, file_path_str: str, project_root: Path) -> Path:
        """file_pathを解決してプロジェクトルートからの絶対パスを返す

        Args:
            file_path_str: ファイルパス文字列
            project_root: プロジェクトルートディレクトリ

        Returns:
            解決されたファイルパス
        """
        app_name = self.ir.meta.name if self.ir.meta else "app"
        file_path = Path(file_path_str)
        if file_path.parts and file_path.parts[0] == "apps":
            file_path = Path(*file_path.parts[1:])
        return project_root / "apps" / app_name / file_path

    def _validate_single_check(self, check: CheckSpec, project_root: Path, errors: dict[str, list[str]]) -> None:
        """単一のCheck関数を検証

        Args:
            check: Check定義
            project_root: プロジェクトルートディレクトリ
            errors: エラーマップ
        """
        if not check.impl or ":" not in check.impl:
            message = f"Check '{check.id}' has invalid impl format: {check.impl}"
            errors["check_functions"].append(message)
            print(f"  ❌ {message}")
            return

        # implパスを解決（file_pathを使って短縮形式をサポート）
        resolved_impl = self._resolve_impl_path(check.impl, check.file_path)
        module_path, func_name = resolved_impl.split(":", 1)

        # file_pathを解決
        expected_file = self._resolve_file_path(check.file_path, project_root)

        try:
            module = importlib.import_module(module_path)
            func = getattr(module, func_name)
            print(f"  ✅ Check {check.id}: function exists")

            # 位置の検証
            self._check_function_location(check.id, "Check", func, expected_file, errors, "check_locations")

        except (ImportError, AttributeError) as exc:
            message = f"Check '{check.id}' not found: {exc}"
            errors["check_functions"].append(message)
            print(f"  ❌ {message}")

    def _validate_transforms(self, project_root: Path, errors: dict[str, list[str]]) -> None:
        """Transform関数の存在、位置、シグネチャを検証

        Args:
            project_root: プロジェクトルートディレクトリ
            errors: エラーマップ
        """
        if not self.ir.transforms:
            return

        print("\n📋 Validating Transform functions:")
        print("=" * 80)

        for transform in self.ir.transforms:
            self._validate_single_transform(transform, project_root, errors)

        print("=" * 80)

    def _validate_single_transform(
        self, transform: TransformSpec, project_root: Path, errors: dict[str, list[str]]
    ) -> None:
        """単一のTransform関数を検証

        Args:
            transform: Transform定義
            project_root: プロジェクトルートディレクトリ
            errors: エラーマップ
        """
        if not transform.impl or ":" not in transform.impl:
            message = f"Transform '{transform.id}' has invalid impl format: {transform.impl}"
            errors["transform_functions"].append(message)
            print(f"  ❌ {message}")
            return

        # implパスを解決（file_pathを使って短縮形式をサポート）
        resolved_impl = self._resolve_impl_path(transform.impl, transform.file_path)
        module_path, func_name = resolved_impl.split(":", 1)

        # file_pathを解決
        expected_file = self._resolve_file_path(transform.file_path, project_root)

        try:
            module = importlib.import_module(module_path)
            func = getattr(module, func_name)
            print(f"  ✅ Transform {transform.id}: function exists")

            # 位置の検証
            self._check_function_location(transform.id, "Transform", func, expected_file, errors, "transform_locations")

            # シグネチャの検証
            self._check_transform_signature(transform, func, errors)

        except (ImportError, AttributeError) as exc:
            message = f"Transform '{transform.id}' not found: {exc}"
            errors["transform_functions"].append(message)
            print(f"  ❌ {message}")

    def _validate_generators(self, project_root: Path, errors: dict[str, list[str]]) -> None:
        """Generator関数の存在、位置、シグネチャを検証

        Args:
            project_root: プロジェクトルートディレクトリ
            errors: エラーマップ
        """
        if not self.ir.generators:
            return

        print("\n📋 Validating Generator functions:")
        print("=" * 80)

        for generator in self.ir.generators:
            self._validate_single_generator(generator, project_root, errors)

        print("=" * 80)

    def _validate_single_generator(
        self, generator: GeneratorDef, project_root: Path, errors: dict[str, list[str]]
    ) -> None:
        """単一のGenerator関数を検証

        Args:
            generator: Generator定義
            project_root: プロジェクトルートディレクトリ
            errors: エラーマップ
        """
        if not generator.impl or ":" not in generator.impl:
            message = f"Generator '{generator.id}' has invalid impl format: {generator.impl}"
            errors["generator_functions"].append(message)
            print(f"  ❌ {message}")
            return

        # implパスを解決（file_pathを使って短縮形式をサポート）
        resolved_impl = self._resolve_impl_path(generator.impl, generator.file_path)
        module_path, func_name = resolved_impl.split(":", 1)

        # file_pathを解決
        expected_file = self._resolve_file_path(generator.file_path, project_root)

        try:
            module = importlib.import_module(module_path)
            func = getattr(module, func_name)
            print(f"  ✅ Generator {generator.id}: function exists")

            # 位置の検証
            self._check_function_location(generator.id, "Generator", func, expected_file, errors, "generator_locations")

            # シグネチャの検証
            self._check_generator_signature(generator, func, errors)

        except (ImportError, AttributeError) as exc:
            message = f"Generator '{generator.id}' not found: {exc}"
            errors["generator_functions"].append(message)
            print(f"  ❌ {message}")

    @staticmethod
    def _check_function_location(
        entity_id: str,
        entity_type: str,
        func: Callable[..., Any],
        expected_file: Path,
        errors: dict[str, list[str]],
        error_category: str,
    ) -> None:
        """関数の位置を検証

        Args:
            entity_id: エンティティID
            entity_type: エンティティタイプ（Check, Transform, Generator）
            func: 関数オブジェクト
            expected_file: 期待されるファイルパス
            errors: エラーマップ
            error_category: エラーカテゴリ
        """
        try:
            actual_file = Path(inspect.getfile(func)).resolve()
            expected_file_resolved = expected_file.resolve()
            if actual_file != expected_file_resolved:
                message = (
                    f"{entity_type} '{entity_id}' location mismatch:\n"
                    f"    Expected: {expected_file}\n"
                    f"    Actual:   {actual_file}"
                )
                errors[error_category].append(message)
                print(f"  ⚠️  {message}")
        except (TypeError, OSError) as exc:
            message = f"{entity_type} '{entity_id}' location could not be determined: {exc}"
            errors[error_category].append(message)
            print(f"  ⚠️  {message}")

    @staticmethod
    def _check_transform_signature(
        transform: TransformSpec, func: Callable[..., Any], errors: dict[str, list[str]]
    ) -> None:
        """Transform関数のシグネチャを検証

        Args:
            transform: Transform定義
            func: 関数オブジェクト
            errors: エラーマップ
        """
        signature = inspect.signature(func)
        expected_params = {p.name for p in transform.parameters}
        actual_params = set(signature.parameters.keys())

        if expected_params != actual_params:
            message = (
                f"Transform '{transform.id}' signature mismatch (file: {transform.file_path}):\n"
                f"    Expected params: {sorted(expected_params)}\n"
                f"    Actual params:   {sorted(actual_params)}"
            )
            errors["transform_signatures"].append(message)
            print(f"  ⚠️  {message}")

    @staticmethod
    def _check_generator_signature(
        generator: GeneratorDef, func: Callable[..., Any], errors: dict[str, list[str]]
    ) -> None:
        """Generator関数のシグネチャを検証

        Args:
            generator: Generator定義
            func: 関数オブジェクト
            errors: エラーマップ
        """
        signature = inspect.signature(func)
        expected_params = {p.name for p in generator.parameters}
        actual_params = set(signature.parameters.keys())

        if expected_params != actual_params:
            message = (
                f"Generator '{generator.id}' signature mismatch:\n"
                f"    Expected params: {sorted(expected_params)}\n"
                f"    Actual params:   {sorted(actual_params)}"
            )
            errors["generator_signatures"].append(message)
            print(f"  ⚠️  {message}")

    def _clear_module_cache(self) -> None:
        """モジュールキャッシュをクリア

        テスト環境でファイルが変更された場合、古いモジュールがキャッシュされているため、
        関連するモジュールをsys.modulesから削除する。
        """
        # apps.で始まるモジュールをキャッシュから削除
        # apps.sample-project.* のような形式のモジュールも含む
        app_name = self.ir.meta.name if self.ir.meta else "app"
        prefixes = ["apps.", f"apps.{app_name}."]
        modules_to_remove = [name for name in sys.modules if any(name.startswith(prefix) for prefix in prefixes)]
        for module_name in modules_to_remove:
            del sys.modules[module_name]

    @staticmethod
    def _summarize_integrity(errors: dict[str, list[str]]) -> None:
        """Integrity検証結果のサマリーを表示

        Args:
            errors: エラーマップ
        """
        print("\n📊 Integrity Validation Summary:")
        print("=" * 80)

        total_errors = sum(len(errs) for errs in errors.values())
        if total_errors == 0:
            print("  ✅ All integrity checks passed!")
        else:
            print(f"  ❌ Total errors: {total_errors}")
            for category, err_list in errors.items():
                if err_list:
                    print(f"    - {category}: {len(err_list)} error(s)")

        print("=" * 80)
