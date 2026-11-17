import type { CodegenConfig } from "@graphql-codegen/cli";
const config: CodegenConfig = {
  schema: "../../services/gateway/schema.graphql",
  documents: "src/shared/api/*.graphql",
  generates: {
    "src/shared/api/generated.ts": {
      plugins: ["typescript-operations", "typed-document-node"],
    },
  },
};
export default config;
