"""Integrity検証エンジン

仕様（SpecIR）と実装の整合性を検証する。
Check/Transform/Generator関数の存在、位置、シグネチャを検証する。
"""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path
from typing import Any

from spectool.core.base.ir import CheckSpec, GeneratorDef, SpecIR, TransformSpec


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

    def _resolve_impl_path(self, impl: str) -> str:
        """implパスを解決（apps. プレフィックスをプロジェクト名を含む形に変換）

        Args:
            impl: 元のimplパス (例: "apps.checks:func")

        Returns:
            解決されたimplパス (例: "apps.sample-project.checks:func")
        """
        if not impl.startswith("apps."):
            return impl

        # プロジェクト名を取得
        app_name = self.ir.meta.name if self.ir.meta else "app"

        # "apps." の後の部分を取得
        rest = impl[5:]  # "apps." を除去

        # "apps.<project-name>." + 残りの部分
        return f"apps.{app_name}.{rest}"

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

        # implパスを解決
        resolved_impl = self._resolve_impl_path(check.impl)
        module_path, func_name = resolved_impl.split(":", 1)

        # file_pathからapps/ プレフィックスを除去して、app_rootを考慮したパスを作成
        app_name = self.ir.meta.name if self.ir.meta else "app"
        file_path = Path(check.file_path)
        if file_path.parts and file_path.parts[0] == "apps":
            file_path = Path(*file_path.parts[1:])
        expected_file = project_root / "apps" / app_name / file_path

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

        # implパスを解決
        resolved_impl = self._resolve_impl_path(transform.impl)
        module_path, func_name = resolved_impl.split(":", 1)

        # file_pathからapps/ プレフィックスを除去して、app_rootを考慮したパスを作成
        app_name = self.ir.meta.name if self.ir.meta else "app"
        file_path = Path(transform.file_path)
        if file_path.parts and file_path.parts[0] == "apps":
            file_path = Path(*file_path.parts[1:])
        expected_file = project_root / "apps" / app_name / file_path

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

        # implパスを解決
        resolved_impl = self._resolve_impl_path(generator.impl)
        module_path, func_name = resolved_impl.split(":", 1)

        # file_pathからapps/ プレフィックスを除去して、app_rootを考慮したパスを作成
        app_name = self.ir.meta.name if self.ir.meta else "app"
        file_path = Path(generator.file_path)
        if file_path.parts and file_path.parts[0] == "apps":
            file_path = Path(*file_path.parts[1:])
        expected_file = project_root / "apps" / app_name / file_path

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

    def _check_function_location(
        self,
        entity_id: str,
        entity_type: str,
        func: Any,
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

    def _check_transform_signature(self, transform: TransformSpec, func: Any, errors: dict[str, list[str]]) -> None:
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

    def _check_generator_signature(self, generator: GeneratorDef, func: Any, errors: dict[str, list[str]]) -> None:
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
        modules_to_remove = [
            name for name in sys.modules if any(name.startswith(prefix) for prefix in prefixes)
        ]
        for module_name in modules_to_remove:
            del sys.modules[module_name]

    def _summarize_integrity(self, errors: dict[str, list[str]]) -> None:
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
