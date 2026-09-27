import { describe, expect, it, vi } from 'vitest';

vi.mock('monaco-editor', () => ({
  languages: {
    getLanguages: () => [
      { id: 'javascript', aliases: ['JavaScript', 'js'], extensions: ['.js', '.mjs'] },
      { id: 'python', aliases: ['Python', 'py'], extensions: ['.py'] },
    ],
  },
}));

import { filenameForLanguage, languageSuggestions, resolveMonacoLanguage } from './languages';

describe('Monaco language support', () => {
  it('offers registered language identifiers and aliases', () => {
    expect(languageSuggestions).toEqual(['javascript', 'JavaScript', 'js', 'py', 'python', 'Python']);
  });

  it('resolves identifiers and aliases without changing the API language value', () => {
    expect(resolveMonacoLanguage('JS')).toBe('javascript');
    expect(resolveMonacoLanguage('Elixir')).toBe('plaintext');
  });

  it('uses a known extension or a neutral filename for unknown languages', () => {
    expect(filenameForLanguage('py')).toBe('main.py');
    expect(filenameForLanguage('Elixir')).toBe('main.txt');
  });
});
