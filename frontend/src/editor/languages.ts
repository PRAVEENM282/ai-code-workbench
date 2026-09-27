import * as monaco from 'monaco-editor';

const registeredLanguages = monaco.languages.getLanguages();

export const languageSuggestions = [...new Set(registeredLanguages.flatMap(({ id, aliases = [] }) => [
  id,
  ...aliases.filter((alias) => alias.trim().length > 0),
]))].sort((left, right) => left.localeCompare(right));

export function resolveMonacoLanguage(language: string): string {
  const requested = language.trim().toLocaleLowerCase();
  return registeredLanguages.find(({ id, aliases = [] }) => (
    id.toLocaleLowerCase() === requested
    || aliases.some((alias) => alias.toLocaleLowerCase() === requested)
  ))?.id ?? 'plaintext';
}

export function filenameForLanguage(language: string): string {
  const requested = language.trim().toLocaleLowerCase();
  const definition = registeredLanguages.find(({ id, aliases = [] }) => (
    id.toLocaleLowerCase() === requested
    || aliases.some((alias) => alias.toLocaleLowerCase() === requested)
  ));
  const extension = definition?.extensions?.find((candidate) => candidate.startsWith('.') && candidate.length > 1);
  return extension ? `main${extension}` : 'main.txt';
}
