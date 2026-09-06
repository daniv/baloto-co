import js from '@eslint/js'
import eslintConfigPrettier from 'eslint-config-prettier'
import jsdoc from 'eslint-plugin-jsdoc'
import vue from 'eslint-plugin-vue'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist/**', 'node_modules/**'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...vue.configs['flat/recommended'],
  {
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: { ...globals.browser, ...globals.node },
      parserOptions: {
        parser: tseslint.parser,
      },
    },
    plugins: { jsdoc },
    rules: {
      'vue/multi-word-component-names': 'off',
      'jsdoc/require-jsdoc': [
        'warn',
        {
          publicOnly: true,
          require: {
            FunctionDeclaration: true,
            ArrowFunctionExpression: true,
          },
        },
      ],
      'jsdoc/require-param': 'off',
      'jsdoc/require-returns': 'off',
    },
  },
  eslintConfigPrettier,
)
