from pathlib import Path

from app.schema import schema

if __name__ == "__main__":
    Path(__file__).with_name("schema.graphql").write_text(schema.as_str() + "\n", encoding="utf-8")
