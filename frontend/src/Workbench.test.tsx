import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import copy from './locales/en.json';
import { Workbench } from './Workbench';

const apiMocks = vi.hoisted(() => ({
  generate: vi.fn(),
  analyze: vi.fn(),
  history: vi.fn().mockResolvedValue([]),
  health: vi.fn().mockResolvedValue({ status: 'ok' }),
}));

vi.mock('./api/client', () => ({
  ApiError: class ApiError extends Error { constructor(message: string, readonly status: number) { super(message); } },
  api: apiMocks,
}));

vi.mock('@monaco-editor/react', () => ({
  default: ({ language, onChange, value }: { language: string; onChange?: (value: string) => void; value: string }) => (
    <textarea
      aria-label="Source code"
      data-language={language}
      onChange={(event) => onChange?.(event.target.value)}
      value={value}
    />
  ),
}));

describe('Workbench', () => {
  beforeEach(() => { cleanup(); vi.clearAllMocks(); });

  it('updates Monaco language and falls back to plaintext for unknown languages', () => {
    render(<Workbench />);

    const language = screen.getByRole('combobox', { name: copy.editor.language });
    const editor = screen.getByRole('textbox', { name: copy.editor.sourceCode });
    expect(editor).toHaveAttribute('data-language', 'python');

    fireEvent.change(language, { target: { value: 'javascript' } });
    expect(editor).toHaveAttribute('data-language', 'javascript');

    fireEvent.change(language, { target: { value: 'madeuplang' } });
    expect(editor).toHaveAttribute('data-language', 'plaintext');
  });

  it('sends an arbitrary language name unchanged to generation', async () => {
    apiMocks.generate.mockResolvedValue({ code: 'puts :hello', routed_model: 'test/model' });
    render(<Workbench />);

    fireEvent.change(screen.getByRole('combobox', { name: copy.editor.language }), { target: { value: 'elixir' } });
    fireEvent.change(screen.getByLabelText(copy.prompt.label), { target: { value: 'Write a hello world program' } });
    fireEvent.click(screen.getByRole('button', { name: copy.actions.generate }));

    await waitFor(() => expect(apiMocks.generate).toHaveBeenCalledWith('Write a hello world program', 'elixir', 'boilerplate'));
  });

  it('shows the analyzer capability notice returned by the backend', async () => {
    apiMocks.analyze.mockResolvedValue({
      static_analysis: [],
      llm_feedback: [],
      analysis_errors: ['No static analysis tool is configured for Rust; AI review is still available.'],
      routed_model: 'test/model',
    });
    render(<Workbench />);
    fireEvent.change(screen.getByLabelText(copy.editor.sourceCode), { target: { value: 'fn main() {}' } });
    fireEvent.change(screen.getByRole('combobox', { name: copy.editor.language }), { target: { value: 'Rust' } });
    fireEvent.click(screen.getByRole('button', { name: copy.actions.analyze }));

    expect(await screen.findByText(/No static analysis tool is configured for Rust/)).toBeInTheDocument();
  });
});
