"""Vertex AI 向け JSON スキーマ変換ユーティリティ

Pydantic v2 の model_json_schema() は $defs でネストモデルを参照するが、
Vertex AI の GenerationConfig は $defs を非サポート。
このモジュールは $ref を再帰的に展開してフラットなスキーマに変換する。
"""
import copy


def flatten_schema(schema: dict) -> dict:
    """$defs の $ref 参照をインライン展開して Vertex AI に渡せる形式に変換する。"""
    schema = copy.deepcopy(schema)
    defs = schema.pop("$defs", {})

    def resolve(obj: any) -> any:
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref_name = obj["$ref"].split("/")[-1]
                return resolve(copy.deepcopy(defs[ref_name]))
            return {k: resolve(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [resolve(item) for item in obj]
        return obj

    return resolve(schema)
