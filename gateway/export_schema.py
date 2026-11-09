import sys
from pathlib import Path

from app.schema import schema

if __name__ == "__main__":
    schema_path = Path(__file__).with_name("schema.graphql")
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            schema_path = Path(sys.argv[idx + 1])
    generated = schema.as_str() + "\n"
    if "--check" in sys.argv:
        if not schema_path.is_file():
            print(f"ERROR: {schema_path} does not exist.", file=sys.stderr)
            sys.exit(1)
        current = schema_path.read_text(encoding="utf-8")
        if current != generated:
            print(
                f"ERROR: {schema_path} has drifted from Gateway schema definition.",
                file=sys.stderr,
            )
            sys.exit(1)
        print("Gateway schema is synchronized.")
        sys.exit(0)
    with open(schema_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(generated)
