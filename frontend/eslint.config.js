export default [
  { ignores: ["dist/**"] },
  {
    files: ["**/*.{js,jsx}"],
    languageOptions: { parserOptions: { ecmaFeatures: { jsx: true } } },
    rules: {
      "eqeqeq": "error",
      "no-undef": "error",
      "no-unreachable": "error",
    },
  },
  {
    files: ["src/**/*.{js,jsx}"],
    languageOptions: { globals: { document: "readonly", window: "readonly", URLSearchParams: "readonly", URL: "readonly", Blob: "readonly", crypto: "readonly" } },
  },
];
