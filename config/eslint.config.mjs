import { createRequire } from 'node:module';

const moduleRoot = process.env.WORKBENCH_NODE_MODULES_DIR ?? process.cwd();
const require = createRequire(`${moduleRoot}/package.json`);
const tseslint = require('typescript-eslint');

export default tseslint.config(
  ...tseslint.configs.recommended,
  {
    files: ['**/*.js', '**/*.mjs', '**/*.ts', '**/*.tsx'],
    rules: {
      'no-eval': 'error',
      'no-implied-eval': 'error',
      'no-new-func': 'error',
    },
  },
);
