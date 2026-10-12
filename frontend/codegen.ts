import type { CodegenConfig } from "@graphql-codegen/cli";
const config: CodegenConfig = {
  schema: "../gateway/schema.graphql",
  documents: ["src/graphql/operations/*.graphql"],
  generates: {
    "src/graphql/generated/": {
      preset: "client",
      config: { useTypeImports: true },
      presetConfig: { fragmentMasking: false },
    },
  },
};
export default config;
