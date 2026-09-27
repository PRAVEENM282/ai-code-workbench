import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { ApiError, api } from './api/client';
import type { AnalyzeResponse, Finding, GenerateResponse, HistoryItem, Language, TaskType } from './api/types';
import { CodeEditor } from './components/CodeEditor';
import { filenameForLanguage, languageSuggestions, resolveMonacoLanguage } from './editor/languages';
import copy from './locales/en.json';

type Result =
  | { kind: 'generate'; data: GenerateResponse }
  | { kind: 'analyze'; data: AnalyzeResponse };
type Action = 'generate' | 'analyze';

export function Workbench() {
  const [language, setLanguage] = useState<Language>('python');
  const [taskType, setTaskType] = useState<TaskType>('boilerplate');
  const [source, setSource] = useState('');
  const [instruction, setInstruction] = useState('');
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState<Action | null>(null);
  const [lastAction, setLastAction] = useState<Action>('generate');
  const [error, setError] = useState<{ message: string; offline: boolean } | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyFailed, setHistoryFailed] = useState(false);
  const [online, setOnline] = useState<boolean | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [paletteQuery, setPaletteQuery] = useState('');

  const findings = useMemo<Finding[]>(() => result?.kind === 'analyze'
    ? [...result.data.static_analysis, ...result.data.llm_feedback]
    : [], [result]);

  const refreshHistory = useCallback(async () => {
    try {
      setHistory(await api.history());
      setHistoryFailed(false);
    } catch {
      setHistoryFailed(true);
    }
  }, []);

  useEffect(() => {
    void refreshHistory();
    void api.health().then(() => setOnline(true)).catch(() => setOnline(false));
  }, [refreshHistory]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
      if (event.key === 'Escape') setPaletteOpen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  const runAction = useCallback(async (action: Action) => {
    setLastAction(action);
    setError(null);
    if (action === 'generate' && !instruction.trim()) {
      setError({ message: copy.results.noPrompt, offline: false });
      return;
    }
    if (action === 'analyze' && !source.trim()) {
      setError({ message: copy.editor.emptyDescription, offline: false });
      return;
    }
    setBusy(action);
    try {
      if (action === 'generate') {
        const data = await api.generate(instruction, language, taskType);
        setResult({ kind: 'generate', data });
      } else {
        const data = await api.analyze(source, language, taskType);
        setResult({ kind: 'analyze', data });
      }
      setOnline(true);
      await refreshHistory();
    } catch (cause) {
      const networkError = cause instanceof ApiError && cause.status === 0;
      setOnline(networkError ? false : online);
      setError({
        message: cause instanceof Error ? cause.message : copy.results.errorTitle,
        offline: networkError,
      });
    } finally {
      setBusy(null);
    }
  }, [instruction, language, online, refreshHistory, source, taskType]);

  const taskOptions = Object.entries(copy.taskTypes) as Array<[TaskType, string]>;
  const commandOptions = [
    { label: copy.commandPalette.generate, action: 'generate' as const },
    { label: copy.commandPalette.analyze, action: 'analyze' as const },
  ].filter((item) => item.label.toLowerCase().includes(paletteQuery.toLowerCase()));

  return (
    <main className="workbench" aria-label={copy.accessibility.workspace}>
      <header className="topbar">
        <div className="brand"><span className="brand-mark" aria-hidden="true">W</span><span>{copy.app.name}</span></div>
        <div className="topbar-center">{copy.app.workspace}<span className="slash">/</span>{copy.editor.sourceCode}</div>
        <div className={`connection ${online === false ? 'is-offline' : ''}`} role="status">
          <span className="connection-dot" />{online === null ? copy.app.checking : online ? copy.app.online : copy.app.offline}
        </div>
        <button className="palette-trigger" onClick={() => setPaletteOpen(true)} aria-label={copy.actions.commandPalette}>
          <span>⌘ K</span>
        </button>
      </header>

      <div className="workspace-grid">
        <aside className="history-pane" aria-label={copy.accessibility.history}>
          <div className="pane-heading"><h2>{copy.history.title}</h2><span className="count">{history.length}</span></div>
          {historyFailed ? (
            <div className="history-state" role="status"><p>{copy.history.error}</p><button className="text-button" onClick={() => void refreshHistory()}>{copy.history.retry}</button></div>
          ) : history.length === 0 ? (
            <div className="history-state" role="status"><span className="empty-glyph">◷</span><p>{copy.history.empty}</p></div>
          ) : (
            <ul className="history-list">
              {history.map((item) => (
                <li key={item.id}>
                  <button className="history-item" onClick={() => {
                    setLanguage(item.language);
                    if (item.endpoint_used === 'analyze') setSource(item.user_input);
                    else setInstruction(item.user_input);
                    if (item.response_payload && 'static_analysis' in item.response_payload) {
                      setResult({ kind: 'analyze', data: item.response_payload });
                    } else if (item.response_payload && 'code' in item.response_payload) {
                      setResult({ kind: 'generate', data: item.response_payload });
                      setSource(item.response_payload.code);
                    }
                  }}>
                    <span className="history-item-title">{copy.taskTypes[item.task_type as TaskType] ?? item.task_type}</span>
                    <span className="history-item-meta">{item.language}<span>·</span>{new Date(item.created_at).toLocaleTimeString()}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="history-footer"><span className="activity-dot" />{copy.app.name}</div>
        </aside>

        <section className="editor-column">
          <div className="editor-toolbar" aria-label={copy.accessibility.editorToolbar}>
            <div className="file-tab"><span className="file-icon">⌘</span><span>{filenameForLanguage(language)}</span><span className="file-dirty" aria-label={copy.editor.unsaved}>●</span></div>
            <div className="editor-controls">
              <label className="sr-only" htmlFor="language-select">{copy.editor.language}</label>
              <input
                id="language-select"
                aria-label={copy.editor.language}
                list="monaco-language-options"
                value={language}
                onChange={(event) => setLanguage(event.target.value)}
                placeholder={copy.editor.languagePlaceholder}
                autoComplete="off"
                spellCheck={false}
              />
              <datalist id="monaco-language-options">
                {languageSuggestions.map((suggestion) => <option key={suggestion} value={suggestion} />)}
              </datalist>
              <button className="icon-button" onClick={() => { setResult(null); setError(null); }} aria-label={copy.actions.clear}>×</button>
            </div>
          </div>

          {!source && !result ? (
            <div className="editor-empty">
              <div className="empty-code-icon" aria-hidden="true">{'{ }'}</div>
              <h2>{copy.editor.emptyTitle}</h2>
              <p>{copy.editor.emptyDescription}</p>
            </div>
          ) : null}
          <div className="editor-surface" data-empty={!source && !result}>
            <CodeEditor
              language={resolveMonacoLanguage(language)}
              value={source}
              findings={findings}
              onChange={setSource}
              onAnalyze={() => void runAction('analyze')}
              onGenerate={() => void runAction('generate')}
            />
          </div>

          <div className="instruction-area">
            <label htmlFor="instruction-input">{copy.prompt.label}</label>
            <div className="instruction-row">
              <textarea
                id="instruction-input"
                value={instruction}
                onChange={(event) => setInstruction(event.target.value)}
                placeholder={copy.prompt.placeholder}
                rows={2}
              />
              <div className="action-stack">
                <button className="primary-action" disabled={busy !== null} onClick={() => void runAction('generate')}>
                  {busy === 'generate' ? <span className="button-spinner" aria-hidden="true" /> : <span aria-hidden="true">✳</span>}{copy.actions.generate}
                </button>
                <button className="secondary-action" disabled={busy !== null} onClick={() => void runAction('analyze')}>
                  {busy === 'analyze' ? <span className="button-spinner" aria-hidden="true" /> : <span aria-hidden="true">⌕</span>}{copy.actions.analyze}
                </button>
              </div>
            </div>
            <div className="instruction-footer">
              <div className="task-select-wrap">
                <label htmlFor="task-select">{copy.editor.task}</label>
                <select id="task-select" value={taskType} onChange={(event) => setTaskType(event.target.value as TaskType)}>
                  {taskOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </div>
              <span className="shortcut-hint"><kbd>⌘</kbd><kbd>↵</kbd> {copy.actions.analyze}</span>
            </div>
          </div>
        </section>

        <aside className="results-pane" aria-label={copy.accessibility.results} aria-live="polite">
          <div className="pane-heading"><h2>{copy.results.title}</h2>{busy ? <span className="working-indicator">{copy.results.loading}</span> : null}</div>
          {error ? (
            <div className="request-error" role="alert">
              <div className="error-icon" aria-hidden="true">!</div>
              <h3>{error.offline ? copy.results.offlineTitle : copy.results.errorTitle}</h3>
              <p>{error.message}</p>
              <button className="retry-action" onClick={() => void runAction(lastAction)}>{copy.actions.retry}</button>
            </div>
          ) : busy ? (
            <div className="result-skeleton" aria-busy="true" aria-label={copy.results.loading}><span /><span /><span /></div>
          ) : !result ? (
            <div className="results-empty" role="status"><span className="result-empty-icon">⌁</span><p>{copy.results.empty}</p></div>
          ) : result.kind === 'generate' ? (
            <div className="result-content">
              <div className="result-status"><span className="success-icon">✓</span>{copy.results.success}</div>
              <ResultMeta model={result.data.routed_model} />
              <ResultSection title={copy.results.generatedCode} findings={[]}>
                <pre className="code-result"><code>{result.data.code}</code></pre>
                <button className="text-button" onClick={() => setSource(result.data.code)}>{copy.actions.replaceEditor}</button>
              </ResultSection>
              {result.data.explanation ? <ResultSection title={copy.results.explanation}><p>{result.data.explanation}</p></ResultSection> : null}
            </div>
          ) : (
            <div className="result-content">
              <div className="result-status"><span className="success-icon">✓</span>{copy.results.success}</div>
              <ResultMeta model={result.data.routed_model} />
              {result.data.analysis_errors?.length ? (
                <div className="partial-notice" role="status">
                  <p>{copy.results.partial}</p>
                  <ul>{result.data.analysis_errors.map((message) => <li key={message}>{message}</li>)}</ul>
                </div>
              ) : null}
              <ResultSection title={copy.results.staticAnalysis} findings={result.data.static_analysis} />
              <ResultSection title={copy.results.aiFeedback} findings={result.data.llm_feedback} />
            </div>
          )}
        </aside>
      </div>

      {paletteOpen ? (
        <div className="palette-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setPaletteOpen(false); }}>
          <section className="command-palette" role="dialog" aria-modal="true" aria-labelledby="palette-title">
            <h2 id="palette-title">{copy.commandPalette.title}</h2>
            <label className="sr-only" htmlFor="palette-search">{copy.commandPalette.search}</label>
            <input id="palette-search" autoFocus value={paletteQuery} onChange={(event) => setPaletteQuery(event.target.value)} placeholder={copy.commandPalette.search} />
            <div className="palette-options">
              {commandOptions.map((item) => <button key={item.action} onClick={() => { setPaletteOpen(false); void runAction(item.action); }}>{item.label}<kbd>↵</kbd></button>)}
            </div>
            <button className="palette-close" onClick={() => setPaletteOpen(false)}>{copy.actions.close}</button>
          </section>
        </div>
      ) : null}
    </main>
  );
}

function ResultMeta({ model }: { model: string }) {
  return <div className="result-meta"><span>{copy.results.model}</span><code>{model}</code></div>;
}

function ResultSection({ title, findings, children }: { title: string; findings?: Finding[]; children?: ReactNode }) {
  return (
    <section className="result-section">
      <div className="result-section-heading"><h3>{title}</h3><span>{findings ? findings.length : ''}</span></div>
      {children ?? (findings?.length ? (
        <ul className="finding-list">
          {findings.map((finding, index) => <li key={`${finding.line_number}-${finding.rule ?? finding.issue_type}-${index}`}>
            <span className={`finding-severity severity-${finding.severity ?? finding.issue_type ?? 'info'}`} />
            <div><p>{finding.message ?? finding.description}</p><small>{copy.results.line} {finding.line_number}{finding.tool ? ` · ${finding.tool}` : ''}</small>
              {finding.suggested_fix ? <p className="suggested-fix">{finding.suggested_fix}</p> : null}</div>
          </li>)}
        </ul>
      ) : <p className="no-findings">{copy.results.noFindings}</p>)}
    </section>
  );
}
